# 本地 Qwen3-TTS 配置与使用

Mac App 的音色选择同时提供系统声音和三个 Qwen 中文男声。设置页的“试听”、音频库的“试听片段”和“生成音频”共用当前选择。切换音色或修改 Qwen 倍速后重新生成即可，已生成的文章音频不会自动更改；线上更新仍需要手动发布预览。

## 模型与男声

- 模型：`mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit`，约 2.3 GB（包括语音 tokenizer）。
- `Uncle_Fu`：低沉、成熟男声。
- `Dylan`：北京口音男声。
- `Eric`：四川口音男声。
- 使用固定的平实朗读指令，减少抒情和句尾拖长；最终听感请用 App 试听确认。

上游：[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[MLX Audio](https://github.com/Blaizzy/mlx-audio)、[量化模型](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit)。本项目安装脚本通过 ModelScope 同名镜像下载并逐文件校验 SHA256，不改写上游权重。模型及依赖的许可按各自上游执行。

## 安装

需要 Apple Silicon Mac、Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、ffmpeg/ffprobe。首次安装会访问 PyPI 与 ModelScope，后续生成严格离线。

在项目目录执行：

```bash
python3 script/setup_qwen.py
```

依赖固定在 `script/requirements-qwen.txt`，其中 MLX Audio 0.6.4、MLX 0.32.4。运行环境安装到用户的 Application Support，不修改系统 Python。模型下载使用分块、有限重试与 SHA256 校验；中断后可重跑。默认最多四个下载连接。模型固定在 ModelScope revision `3624a3894b6b8e09d202873a2e240b1326e43128`；清单与下载都使用该版本。SHA 校验失败会清理损坏分块，重跑可重新下载。

如果已有完整的 CustomVoice 模型目录，可复用，无需再下载或复制：

```bash
python3 script/setup_qwen.py --source-model "/absolute/path/to/1.7B-CustomVoice-4bit"
```

安装脚本默认保留并检查已有 `tts.json`。确认需要替换它时，加入 `--replace-config`，并同时提供需要的 `--source-model` 和 `--speed`。不会修改当前选中的音色。

## App 设置

重新打开 App，进入“设置与连接 → 播客”：

1. 音色选择 `Qwen · Uncle_Fu`、`Dylan` 或 `Eric`。
2. 设置 Qwen 倍速，建议先试 **1.25**，可选 **0.75–2.0**。它与系统声音的 180/220/240 语速独立。
3. 如果修改 Python、模型目录或倍速，点击“保存 Qwen 配置”。
4. “检查本机环境”检查当前引擎；“试听”会自动生成并播放短文，支持停止。
5. 回到音频库选中文章，点击“生成音频”。修改音色或倍速后再次生成，会替换本地成品；失败时保留旧成品。

Qwen 参数保存在：

```text
~/Library/Application Support/Wechat2Podcast/Podcast/tts.json
```

配置模板见 `config/qwen.example.json`。新安装的默认路径为：

```text
~/Library/Application Support/Wechat2Podcast/QwenTTS/venv/bin/python
~/Library/Application Support/Wechat2Podcast/QwenTTS/models/1.7B-CustomVoice-4bit
```

使用 `--source-model` 时，配置会指向传入的现有目录；该目录需要持续保留。

## 资源与生成建议

2026-11-03 的 M1/16 GB 独立试听中，旧试验代码生成约 35–46 秒音频，耗时约 38–49 秒，MLX 峰值约 9.1 GB。2026-11-08 男声试听曾与构建同时运行，耗时约为音频的 3–5 倍；这些不是不同音色的严格性能对比。

正式接入的一次 M1/16 GB 两段测试中，生成 23.6 秒成品耗时约 207 秒，MLX 峰值约 6.16 GB；当前机器其他负载未隔离，不能把旧试听时间当作日常速度保证。

正式接入使用每段最多 80 个字符、MLX 缓存上限 256 MiB、段间清缓存，逐段写 WAV，避免整篇音频一直累积在内存。每篇文章加载一次模型；批量处理逐篇进行。长文章应预留充足生成时间，尽量避免同时运行其他占用大量内存的模型任务。需要快速批量生成时，系统婷婷仍是更轻量的选择。

Qwen 原始 WAV 通过保持音高的 `atempo` 调速，最终与现有播客格式一致：24 kHz、单声道、48 kbps MP3。相同正文、音色、模型权重标识、分词器和生成配置、运行时版本及倍速会复用已校验的成品。输出 `audio.json` 保存参数签名、合成耗时和 MLX 峰值；这些是进程指标，不等同于整机内存占用。

点击“停止任务”会终止隔离的 Python/MLX 子进程。中间 WAV 用后清理，已生成的旧 MP3 在新成品校验成功前保留。达到单段生成上限会报错而非静默截断；不自动联网补模型，也不自动上传文章。

## GitHub 提交范围

提交引擎代码、安装脚本、依赖版本、配置模板、测试及本文档。权重、虚拟环境、试听音频、用户实际路径配置和播客内容不进入仓库。`tts.json` 没有云端密钥；它仍属于本机配置，采用用户目录和 0600 权限保存。
