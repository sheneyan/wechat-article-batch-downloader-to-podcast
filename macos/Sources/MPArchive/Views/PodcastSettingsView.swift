import AppKit
import SwiftUI
struct PodcastSettingsView: View {
 @ObservedObject var store: PodcastStore
 var body: some View {
  Form {
   Section("本地文章与音频") {
    TextField("归档目录",text:$store.archive)
    Button("选择归档目录…"){chooseDirectory()}
    Text("下载目录更改在重新打开应用后生效；已有归档继续保留。").font(.caption).foregroundStyle(.secondary)
    TextField("Python 可执行文件",text:$store.python)
    Button("检查本机环境"){Task{await store.checkDependencies()}}.disabled(store.busy)
    Picker("音色",selection:$store.voice){ForEach(store.selectableVoices){Text($0.label).tag($0.id)}}.disabled(store.busy)
    HStack {
     Button(store.playingVoicePreview ? "停止试听" : "试听"){if store.playingVoicePreview {store.stopPlayback()}else{Task{await store.previewVoice()}}}
     Button("刷新本机音色"){Task{await store.loadVoices()}}
    }.disabled(store.busy)
    if store.isQwen {
     Stepper(value:$store.qwenSettings.speed,in:0.75...2.0,step:0.05){Text("Qwen 倍速：\(store.qwenSettings.speed,format:.number.precision(.fractionLength(2)))")}.disabled(store.busy)
     TextField("Qwen Python",text:$store.qwenSettings.python).disabled(store.busy)
     TextField("Qwen 模型目录",text:$store.qwenSettings.model).disabled(store.busy)
     Button("保存 Qwen 配置"){Task{await store.saveQwenSettings()}}.disabled(store.busy || !store.qwenConfigLoaded)
     Text("完全在本机生成，长文章分段处理，可能需要数分钟。倍速与路径修改后请保存配置。").font(.caption).foregroundStyle(.secondary)
    } else {Stepper("语速：\(store.rate)",value:$store.rate,in:80...400,step:10).disabled(store.busy)}
   }
   Section("口播稿收件") {
    TextField("收件 URL",text:$store.inboxSettings.base_url)
    SecureField("读取密钥",text:$store.inboxSettings.read_token)
    Text("仅需读取密钥。点击“拉取口播稿”才会下载；测试稿默认隐藏，拉取后仍需手动生成音频与确认发布。").font(.caption).foregroundStyle(.secondary)
    HStack {Button("保存收件配置"){Task{await store.saveInboxSettings()}};Button("测试已保存的收件配置"){Task{await store.testInbox()}}}.disabled(store.busy)
   }
   Section("服务器 · 手动发布") {
    TextField("节目名称",text:$store.settings.feed_title)
    TextField("HTTPS 播客根地址（含访问路径）",text:$store.settings.base_url)
    TextField("SSH 主机或 ~/.ssh/config 别名",text:$store.settings.ssh_host)
    TextField("SSH 用户（可留空使用 SSH 配置）",text:$store.settings.ssh_user)
    TextField("SSH 端口",value:$store.settings.ssh_port,format:.number.grouping(.never))
    Text("端口设为 22 时遵循 SSH 配置中别名的 Port；填写其他端口会显式覆盖 SSH 配置。").font(.caption).foregroundStyle(.secondary)
    HStack {TextField("私钥路径（可选）",text:$store.settings.identity_file);Button("选择…"){let p = NSOpenPanel();p.canChooseDirectories = false;p.showsHiddenFiles = true;if p.runModal() == .OK,let url = p.url {store.settings.identity_file = url.path}}}
    TextField("服务器存储根目录",text:$store.settings.remote_root)
    Text("使用正常 SSH 配置与已配置的密钥认证。此处部署发布组件，不配置域名、HTTPS 或 nginx；生成音频不会自动上传。").font(.caption).foregroundStyle(.secondary)
    HStack {Button("保存配置"){Task{await store.saveSettings()}};Button("测试已保存的 SSH"){Task{await store.connection()}};Button("部署 / 更新发布组件"){Task{await store.connection(deploy:true)}}}.disabled(store.busy)
   }
   PodcastActivityView(store:store)
  }.formStyle(.grouped).padding(12).task{if !store.configLoaded {await store.loadSettings()};if !store.inboxConfigLoaded {await store.loadInboxSettings()};if !store.qwenConfigLoaded {await store.loadQwenSettings()};if store.voices.isEmpty {await store.loadVoices()}}
 }
 private func chooseDirectory() {let p = NSOpenPanel();p.canChooseDirectories = true;p.canChooseFiles = false;p.canCreateDirectories = true;if p.runModal() == .OK,let url = p.url {store.archive = url.path}}
}
