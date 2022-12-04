import asyncio
import json
import logging
import os
import string
import sys

import httpx
from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, Response
from quart import request
from random import choices


def App(logger, http_client, upstream_root, app_name):
    request_id_alphabet = string.ascii_letters + string.digits

    def get_new_request_id():
        return ''.join(choices(request_id_alphabet, k=8))

    app = Quart(app_name)

    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
    @app.route('/<path:path>', methods=['GET', 'POST'])
    async def handle(path):
        request_id = get_new_request_id()
        request_method = request.method
        logger.info('[%s] Downstream request %s %s', request_id, request_method, path)

        return \
            await handle_lfs_batch(request_id, request_method, path) if path.endswith('.git/info/lfs/objects/batch') else \
            await handle_proxy(request_id, request_method, path)


    async def handle_lfs_batch(request_id, request_method, path):
        data = await request.data
        logger.info('[%s,%s,%s] %s', request_id, request_method, path, data)
        data = json.loads(data)

        lfs_batch_data =  {
            "transfer": "basic",
            "objects": [
                {
                    "oid": obj["oid"],
                    "size": obj["size"],
                    "actions": {
                        "download": {
                            "href": request.url_root + path.removesuffix('.git/info/lfs/objects/batch') + '/lfs/objects/' + obj["oid"][0:2] + '/' + obj["oid"][2:4] + '/' + obj["oid"],
                            "expires_in": 20,
                        },
                    }
                }
                for obj in data['objects']
            ]
        }
        logger.info('[%s,%s,%s] %s', request_id, request_method, path, lfs_batch_data)
        return lfs_batch_data

    async def handle_proxy(request_id, request_method, path):

        upstream_request = http_client.build_request(request.method, upstream_root + '/' + path)
        logger.info('[%s,%s,%s] Upstream request: %s', request_id, request_method, path, upstream_request)

        upstream_response = await http_client.send(upstream_request, stream=True)
        logger.info('[%s,%s,%s] Upstream response: %s', request_id, request_method, path, upstream_response)

        async def downstream_response_bytes():
            l = 0
            remaining_until_log = 10000000
            async for chunk in upstream_response.aiter_bytes(65536):
                l += len(chunk)
                remaining_until_log -= len(chunk)
                if remaining_until_log <= 0:
                    remaining_until_log = 10000000
                    logger.info('[%s,%s,%s] Downstream response: %s bytes so far', request_id, request_method, path, l)
                yield chunk
            logger.info('[%s,%s,%s] Downstream response: %s bytes total', request_id, request_method, path, l)

        return downstream_response_bytes(), upstream_response.status_code, [
            (k, v) for k, v in upstream_response.headers.items()
            if k.lower() not in ('connection', 'transfer-encoding')
        ]

    return app


async def async_main():
    name = os.environ.get('APP_NAME', 'git-lfs-http-mirror')
    logging.basicConfig(stream=sys.stdout, level=os.environ.get('LOG_LEVEL', 'WARNING'))
    logger = logging.getLogger(name)

    logger.info('Starting server')
    upstream_root = os.environ['UPSTREAM_ROOT']
    logger.info('Serving from %s', upstream_root)

    config = Config()
    config.bind = [os.environ.get('BIND', '0.0.0.0:8080')]

    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=3)) as http_client:
        await serve(
            App(logger=logger, http_client=http_client, upstream_root=upstream_root, app_name=name),
            config,
        )
    logger.info('Stopped server')


if __name__ == "__main__":
    asyncio.run(async_main())
