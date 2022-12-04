import json
import logging
import os
import re
import string
import sys
import urllib.parse

import httpx
from flask import Flask, Response, render_template
from flask import request
from random import choices
from waitress import serve


def App(logger, http_client, upstream_root, app_name):
    request_id_alphabet = string.ascii_letters + string.digits

    def get_new_request_id():
        return ''.join(choices(request_id_alphabet, k=8))

    app = Flask(app_name)

    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
    @app.route('/<path:path>', methods=['GET', 'POST'])
    def handle(path):
        request_id = get_new_request_id()
        request_method = request.method
        logger.info('[%s] Downstream request %s %s', request_id, request_method, path)

        return \
            handle_lfs_batch(request_id, request_method, path) if path.endswith('.git/info/lfs/objects/batch') else \
            handle_proxy(request_id, request_method, path)


    def handle_lfs_batch(request_id, request_method, path):
        logger.info('[%s,%s,%s] %s', request_id, request_method, path, request.data)
        data = json.loads(request.data)

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

    def handle_proxy(request_id, request_method, path):

        upstream_request = http_client.build_request(request.method, upstream_root + '/' + path)
        logger.info('[%s,%s,%s] Upstream request: %s', request_id, request_method, path, upstream_request)

        upstream_response = http_client.send(upstream_request, stream=True)
        logger.info('[%s,%s,%s] Upstream response: %s', request_id, request_method, path, upstream_response)

        def downstream_response_bytes():
            l = 0
            remaining_until_log = 10000000
            for chunk in upstream_response.iter_bytes(65536):
                l += len(chunk)
                remaining_until_log -= len(chunk)
                if remaining_until_log <= 0:
                    remaining_until_log = 10000000
                    logger.info('[%s,%s,%s] Downstream response: %s bytes so far', request_id, request_method, path, l)
                yield chunk
            logger.info('[%s,%s,%s] Downstream response: %s bytes total', request_id, request_method, path, l)

        def close_upstream_response():
            upstream_response.close()
            logger.info('[%s,%s,%s] Downstream response: closed', request_id, request_method, path)

        downstream_response = Response(
            downstream_response_bytes(),
            status=upstream_response.status_code,
            headers=[
                (k, v) for k, v in upstream_response.headers.items()
                if k.lower() not in ('connection', 'transfer-encoding')
            ],
        )
        logger.info('[%s,%s,%s] Downstream response: %s', request_id, request_method, path, downstream_response)
        downstream_response.autocorrect_location_header = False
        downstream_response.call_on_close(close_upstream_response)

        return downstream_response

    return app


if __name__ == "__main__":
    name = os.environ.get('NAME', 'git-lfs-proxy')
    logging.basicConfig(stream=sys.stdout, level=os.environ.get('LOG_LEVEL', 'WARNING'))
    logger = logging.getLogger(name)

    logger.info('Starting server')
    upstream_root = os.environ['UPSTREAM_ROOT']
    logger.info('Serving from %s', upstream_root)

    with httpx.Client(transport=httpx.HTTPTransport(retries=3)) as http_client:
        serve(
            App(logger=logger, http_client=http_client, upstream_root=upstream_root, app_name=name),
            host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), threads=16,
        )
    logger.info('Stopped server')
