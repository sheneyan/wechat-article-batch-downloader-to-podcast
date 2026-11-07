# 微信文章播客 · Mac App

基于 [公众号文章下载器](https://github.com/dingaiminGIT/wechat-article-batch-downloader) 扩展的个人 Mac 应用，把文章下载、系统 / 本地 Qwen TTS、本地音频和线上播客放到同一个界面。

侧栏保留原有公众号归档与下载中心，并增加：

- **音频库**：跨公众号统一列表，扫描归档、多选转换、试听、播放、Finder 定位和删除；分别显示本地音频与线上状态，音频版本不同会提示待更新。
- **拉取口播稿**：手动从收件服务下载 Grok 稿件，校验后进入同一音频库；来源可筛选，正文与读音备注分开查看。测试稿默认隐藏且不能转换或发布。
- **在线播客**：查看服务器当前最多 20 集、大小和最近刷新时间；复制 RSS、预览发布、手动下架。网络错误显示未知/待刷新，保留上次列表作参考。
- **设置与连接 → 播客**：归档目录、Python、本机系统 / Qwen 男声音色选择和语速；HTTPS 节目地址、SSH 主机/别名、用户、端口、私钥路径及服务器目录。支持直接试听当前音色与语速、环境检查、SSH 测试和发布组件部署/更新。

**默认手动发布**：下载和生成音频都不会自动上传。发布预览列出将上线/更新和被淘汰的文章，确认后才执行。

## 构建和安装

需要 Apple Silicon Mac、macOS 14+、Xcode/Swift、Go，以及本机 Python 3.11+、ffmpeg/ffprobe。Python 和 ffmpeg 不随 App 打包，设置中可指定 Python 路径；“检查本机环境”会列出缺少的组件。

```sh
./script/build_app.sh --build-only
# 先退出正在运行的本应用，再安装并打开
./script/build_app.sh --install
```

新 App 安装为 `~/Applications/微信文章播客.app`，bundle ID 为 `io.zi5.wechat2podcast`，不会覆盖原“公众号文章下载器”。它使用 `127.0.0.1:2142/2143`，启动时不启用系统代理；连接微信和恢复网络仍沿用上游实现。

音频库选中文章后可点击“删除…”，确认后清理本地记录、完整音频和试听；删除标记会阻止后续扫描或口播稿拉取自动恢复。原始归档文件保留，线上节目需在“在线播客”单独下架。此操作没有 App 内恢复入口。

本地 Qwen 男声支持直接试听和全文生成，安装、配置模板、资源建议见 [本地 Qwen3-TTS 指南](docs/local-qwen-tts.md)。

应用数据在 `~/Library/Application Support/Wechat2Podcast/`。`Podcast/library/` 保存完整文章与音频，`Podcast/publish.json` 保存服务器配置。安装脚本会在目标条目不存在时复制本项目 `.local/library/` 和 `.private/publish.json`，不会覆盖现有 App 数据或删除原文件。

首次访问 Documents 等目录时按 macOS 提示授权。关闭窗口会继续任务；退出时若有音频任务运行，会提示等待或停止。中途停止发布后请刷新线上状态，因为已经到达服务器的原子提交可能完成。

## 服务器配置

外部 Bot 的纯文字口播稿也可先投递到独立收件服务，再由 Mac 拉取。见[口播稿收件接口说明](docs/script-inbox-api.md)。在“设置与连接 → 播客 → 口播稿收件”填写收件地址和独立读取密钥；Grok 持有的写入密钥不能用于 Mac 读取。拉取本身不自动转换或发布，不占用在线音频名额。

微信文章和每日 X 口播共用同一个节目，可在服务器设置中填写节目名称（本机使用“我的订阅”）；部署/更新组件时会重建 RSS 标题，保留单集 GUID 和订阅地址。两种来源合计最多在线 20 集，继续使用发布预览与手动确认。

先配置可用 SSH 密钥/agent 或 `~/.ssh/config`，再在 App 中填写服务器信息。不会保存 SSH 密码或复制私钥内容，只保存私钥路径；默认端口 22 会遵循 SSH 别名里的 Port，非默认值显式覆盖它。首次连接的主机指纹确认需要先通过正常 SSH 完成。

HTTPS 地址可填服务器域名，保存时生成 `/wechat/<随机标识>`，也可填写已有完整节目根地址或 RSS。请保留现有节目标识；同一服务器目录已有节目时，部署会拒绝换成另一标识，避免破坏已有目录。新节目应使用独立服务器目录。

“部署 / 更新发布组件”使用当前已保存的 SSH 配置上传 Python 发布代码和配置，目标目录必须可由 SSH 用户写入。它**不自动申请证书、改 DNS 或修改 nginx**。站点管理员需在已有 HTTPS 虚拟主机中将 `/wechat/` 映射到 `<服务器目录>/www`，关闭目录索引并允许 GET/HEAD 与 Range。命令行可生成 nginx 模板：

```sh
python3 deploy.py --config /path/to/publish.json --nginx-snippet .local/wechat-location.conf
```

修改站点配置后先运行 `nginx -t` 再 reload。音频和 RSS 都由选定存储服务器提供，已有 CardPodcast 中转节点如何下载/压缩它们是独立流程。随机链接不进入发现目录，链接持有者可以读取内容。

## 命令行与存储规则

Mac 保存完整文章和音频，RackNerd 提供统一的「微信文章」播客，最多在线 20 集。

目前支持 `wechat_archived/<公众号>/style_corpus.jsonl` 配合 `markdown/` 的归档格式。保留正文段落、标题、来源、作者、原文时间及链接；图片不做 OCR，图中文字不进入朗读内容。清理只处理排版，不摘要或改写正文。

归档缺少或无法解析原文时间时仍可导入，列表显示“日期未知”。本地单独记录首次导入时间，重复扫描不改变它；发布时将此时间用于 RSS 日期，并在简介中注明原文日期缺失。它也作为缺日期文章的在线排序/淘汰日期，不冒充原文发布时间。

## 使用

需要 Python 3.11+、macOS 系统 `say`、`ffmpeg` 和 `ffprobe`。无第三方 Python 依赖。在本项目目录运行：

```sh
cd wechat-article-batch-downloader-to-podcast
python3 -m wechat2podcast scan
python3 -m wechat2podcast list
```

扫描默认读取 `~/Documents/wechat_archived/`，跨公众号合并，根据微信文章身份去重。扫描只保存在 Mac，不上传；归档源文件不修改。文章 ID 可使用列表中唯一的前缀。

```sh
# 生成约一分钟试听
python3 -m wechat2podcast preview 18d748

# 转换指定文章，或将所有本地文章转好备用
python3 -m wechat2podcast render 18d748
python3 -m wechat2podcast render --all

# 可调整语速和已安装的系统音色
python3 -m wechat2podcast preview 18d748 --voice Tingting --rate 180
```

默认婷婷、语速 180，成品为 24 kHz / 单声道 / 48 kbps MP3。`say` 的 rate 参数不是中文字符每分钟的准确计数，以实际试听为准。AIFF 中间文件用后清理。转换已完成且正文、音色、语速均不变时复用已校验的 MP3。

```sh
# 手动选择一篇或多篇：先预览上线和淘汰清单
python3 -m wechat2podcast publish 18d748 74605f

# 确定后显式发布
python3 -m wechat2podcast publish 18d748 74605f --apply

# 查看线上集合与总音频占用
python3 -m wechat2podcast status

# 查看私人订阅地址
python3 -m wechat2podcast url
```

将 `url` 输出的 RSS 加入 CardPodcast。`.private/subscribe.txt` 中还有 `节目名,RSS地址` 单行，可**追加**到现有 TF 卡 `podcast_list.txt`，不要用这一行覆盖原有整份订阅清单。本工具不自动修改设备。

## 20 集规则

- 扫描、试听、转换永远不自动上传；只有 `publish --apply` 发布。
- 一次最多手动选择 20 篇，同一篇重复发布不重复占位。
- 选中的文章一定上线。如果超额，从原在线集合中按原文发布日期由早到晚淘汰，日期相同以文章 ID 排序。
- 因此可以重新上线一篇很早的文章，它不会因日期太早而被当次淘汰。
- 音频完整上传并校验 SHA256 后，使用文件锁和版本检查，原子切换 RSS 与目录；随后删除不再被引用的服务端 MP3。
- 失败时保留旧 RSS；并发发布使目录变化时拒绝提交，重新预览后再发布。
- 被淘汰文章仍完整留在 Mac，可再次手动发布。设备已下载的文件不受服务端删除影响；尚未下载的旧条目需刷新目录，已淘汰的音频地址会返回 404。
- 发布过程中为安全切换，会短暂同时存放旧音频和本次新音频；发布完成后最多在线 20 篇。短期保留少量旧目录元数据，不保留淘汰音频。
- 20 篇限制的是集数，并非固定字节限额；实际空间与总时长有关。

## 本地数据

均为 Git 忽略目录：

- `.local/library/<文章ID>/article.json`：元数据及完整朗读文本快照。
- `.local/library/<文章ID>/speech.txt`、`audio.mp3`、`audio.json`：完整朗读文本、成品和校验/转换信息。
- `.local/previews/<文章ID>/`：独立试听，不会误用作完整文章发布。
- `.private/publish.json`：SSH 目标和节目地址；`.private/subscribe.txt`：订阅行。

Mac 目前保存每篇文章的最新一次音频。主动改变正文、音色或语速并重新转换，会替换该篇本地成品；正常的服务端淘汰不会删除或替换本地成品。

服务器目录中 `app/` 存放代码，`.staging/` 存放上传暂存，`www/wechat/<随机标识>/` 提供 RSS 和 MP3，`generations/` 保存原子发布所需元数据。无常驻 Python 服务，也不需要公网上传接口。

重新部署保留发布配置，避免改变节目路径。备份时应包含 App 的 Application Support 数据；若使用 CLI，还应包含 `.local/` 和 `.private/`，不要只备份 Git 文件。

## 验证

```sh
python3 -m unittest discover -s tests -v
swift test --package-path macos
python3 script/verify_bundle.py ~/Applications/微信文章播客.app
```

测试覆盖跨公众号归一、去重、Markdown 正文清理、RSS 元数据、20/21 集替换、重复发布、缺失/损坏音频、并发冲突、切换失败及旧文件清理。机器检查无法替代人工试听或 Cardputer 实机播放验收。

## 上游许可

沿用上游的 **Commons Clause + MIT** 条款，并保留 [LICENSE](LICENSE) 及[来源记录](third_party/UPSTREAM.md)。这不是无限制的 MIT；后续对外销售软件或主要依赖其功能的服务，需要另行评估授权。
