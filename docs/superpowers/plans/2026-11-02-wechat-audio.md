# 微信文章音频 Implementation Plan

**Goal:** 将本地微信归档转换为一个可手动发布、在线最多 20 集的播客。

**Architecture:** Python 标准库命令行分离归档读取、TTS、RSS 与远程发布。Mac 持久保存完整库，RackNerd 通过 SSH 接收完整音频并原子更新静态 RSS，以文件锁和版本检查处理并发。

**Tech Stack:** Python 3、unittest、macOS say、ffmpeg/ffprobe、OpenSSH、nginx。

用户已授权继续，在当前新仓库顺序执行，无需创建额外工作区。

1. [x] 创建 `tests/test_core.py`，覆盖跨公众号归一、去重、Markdown 清理、日期、20 集淘汰及 RSS XML。运行 `python3 -m unittest discover -s tests -v` 观察缺失实现失败，再实现 `wechat2podcast/core.py`。
2. [x] 创建 `tests/test_remote.py`，覆盖发布原子性、缺失/校验失败不更新 RSS、版本冲突、替换后清理音频。运行同一测试命令观察失败，再实现 `wechat2podcast/remote.py`。
3. [x] 创建 `wechat2podcast/__main__.py` 与 `audio.py`，提供 scan/list/render/preview/publish/status。转换用 say 文件输入和 ffmpeg 参数数组，不拼接文章到 shell；输出先写临时文件并验证再改名。运行真实 5 篇扫描、1 分钟试听及完整转换。
4. [x] 添加部署脚本/配置和 README。在 RackNerd 建独立目录并部署 Python 包、只读 nginx location；先备份虚拟主机，`nginx -t` 成功后 reload。
5. [x] 预览 5 篇发布计划后显式发布，验证 HTTPS RSS、MP3 SHA256、HEAD 与 Range 206；复查原 `/healthz` 仍工作。保存不含私人 URL 的验证记录，最终报告试听路径和订阅方式。
