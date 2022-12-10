# git-lfs-http-mirror

Python wrapper for git that allows it to read a GET-only HTTP mirror of repositories that use Large File Storage (LFS). It effectively extends git's so-called [dumb git protocol](https://git-scm.com/book/en/v2/Git-on-the-Server-The-Protocols#_dumb_http) with the capability to serve LFS files.

This means you can use S3 to host mirrors of LFS repositories, without additional infrastructure. However, no authentication mechanism is currently supported. From the point of view of the calling code, it must be a publically readable bucket.


## Installation

```bash
pip install git-lfs-http-mirror
```


## Usage

Configuration is by command line arguments

```bash
python -m git_lfs_http_mirror
    --upstream_root 'https://my-bucket.s3.eu-west-2.amazonaws.com/a-folder'
    --bind '127.0.0.1:8080'
    -- git clone http://127.0.0.1:8080/my-repo
```

The server configued as `upstream_root` should be a static server, serving copies of git repositories, for example S3. Each copy can be created using:

```bash
git clone --bare https://server.test/my-repo
cd my-repo.git
git lfs fetch
git update-server-info
````

and then uploaded to the server in its own folder. If the server is S3, this can be done using the Upload folder feature in the AWS S3 Console.


## How it works

The wrapper script temporarily fires up a LFS server during the lifetime of the git command.
