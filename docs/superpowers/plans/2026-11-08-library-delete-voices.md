# 本地删除与音色选择

Goal: 删除所选本地文章记录、完整音频及试听，后续归档扫描与口播稿导入都不再自动恢复。原始下载文件及线上节目独立保留。系统音色从本机声音列表选择；Qwen 本轮提供中文男声试听，待用户选择后接入正式生成。

Architecture: Library 保存按完整文章 ID 记录的删除标记，先校验整个删除批次及受管目录，再持久化标记并清理文件。扫描、文章列表、Grok 导入共用删除标记。SwiftUI 确认删除时固定所选 ID，停止本地播放后调用桥接动作并刷新列表。系统音色由 say -v ? 查询，保留用户原有选择。

- [x] tests/test_library_delete.py: 隔离库验证微信扫描不恢复、Grok 重复导入不恢复、试听清理、非法批次不删除其他文章、目录符号链接不越界。
- [x] wechat2podcast/library.py、script_library.py、gui.py: 实现删除、忽略标记及桥接动作；不调用远端服务。
- [x] macos PodcastStore、PodcastView: 多选删除与确认，成功刷新；操作忙碌时禁用。
- [x] dependencies.py、PodcastSettingsView、PodcastModels: 可用声音查询与下拉选择。
- [x] 完整 Python/Swift 测试，构建安装、签名核验；使用隔离数据验证删除路径，真实库只读。
- [x] 本地 Uncle_Fu、Dylan 试听统一 1.25 倍速度、响度和 MP3 格式。

Validation: Python 62 项、Swift 17 项通过，App 构建安装和运行后签名检查通过。隔离库实际验证删除、微信重新扫描、Grok 重复导入、非法批次与目录符号链接；原生 UI 实测音色菜单和删除确认后取消。原有 24 条 article.json SHA 与音频大小在安装后保持一致。

Qwen 男声两份本地试听已完成：Uncle_Fu 原始 62 秒、合成 189 秒；Dylan 原始 47.2 秒、合成 243 秒，峰值 MLX 9.7 GB（当时同时构建 App，存在内存压力，不能作为独立性能基准）。均导出 1.25 倍速度 MP3；本轮没有接入正式 Qwen 生成菜单。
