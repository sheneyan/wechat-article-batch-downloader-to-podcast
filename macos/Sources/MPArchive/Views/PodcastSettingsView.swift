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
    TextField("系统语音",text:$store.voice)
    Stepper("语速：\(store.rate)",value:$store.rate,in:80...400,step:10)
   }
   Section("服务器 · 手动发布") {
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
  }.formStyle(.grouped).padding(12).task{if !store.configLoaded {await store.loadSettings()}}
 }
 private func chooseDirectory() {let p = NSOpenPanel();p.canChooseDirectories = true;p.canChooseFiles = false;p.canCreateDirectories = true;if p.runModal() == .OK,let url = p.url {store.archive = url.path}}
}
