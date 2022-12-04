# git-lfs-http-mirror

Simple Python server to serve a read only HTTP mirror of git repositories that use Large File Storage (LFS)

Designed to sit in front of another HTTP server that serves git repositories using the so-called [dumb git protocol](https://git-scm.com/book/en/v2/Git-on-the-Server-The-Protocols#_dumb_http), extending it with the capability to serve LFS files.
