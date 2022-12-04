# git-lfs-http-mirror

Simple Python server to serve a read only HTTP mirror of git repositories that use Large File Storage (LFS)

Designed to sit in front of another HTTP server that serves git repositories using the so-called [dumb git protocol](https://git-scm.com/book/en/v2/Git-on-the-Server-The-Protocols#_dumb_http), extending it with the capability to serve LFS files.


## Installation

```bash
pip install git-lfs-http-mirror
```


## Usage

Configuration is by environment variables

```bash
UPSTREAM_ROOT='https://my-bucket.s3.eu-west-2.amazonaws.com/a-folder' \
LOG_LEVEL=INFO \
BIND='0.0.0.0:8080' \
    python -m git_lfs_http_mirror
```

The server configued as `UPSTREAM_ROOT` should be a static server, serving copies of git repositories. Each copy can be created using:

```bash
git clone --bare https://server.test/my-repo
cd my-repo.git
git lfs fetch
git update-server-info
````

and then uploaded to the server in its own folder. If the server is S3, this can be done using the Upload folder feature in the AWS S3 Console.
