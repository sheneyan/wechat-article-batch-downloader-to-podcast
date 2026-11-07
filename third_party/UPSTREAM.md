# Upstream attribution

This repository is based on the user's fork of
[dingaiminGIT/wechat-article-batch-downloader](https://github.com/dingaiminGIT/wechat-article-batch-downloader),
at upstream commit `b723c353c82a946f5a4254d11067fdb1ae7ede25`.

The original downloader is derived from `wx_channels_download`. Its license is
MIT with the Commons Clause condition, **not unrestricted MIT**. The original
root `LICENSE`, Go dependency license files, and
`third_party/wechat-article-batch-downloader.LICENSE` are retained. Do not remove
the upstream copyright or Commons Clause when copying or distributing the app.

Additions in this fork: macOS text-to-speech, complete local audio library,
bounded manual online publication, SSH server configuration, and native
SwiftUI library/publication management. The Go downloader is retained; the Mac
wrapper uses a distinct app identifier, data directory, and local ports to
avoid overwriting the separately installed upstream application.

The current local build is for the user's personal workflow. Any later
commercial distribution needs a separate evaluation of the upstream terms.
