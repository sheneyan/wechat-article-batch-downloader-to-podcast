import SwiftUI
import AppKit
struct OnlinePodcastView: View {
 @ObservedObject var store: PodcastStore
 var body: some View {
  VStack(alignment:.leading,spacing:12) {
   HStack {VStack(alignment:.leading,spacing:4){if let online = store.online {Text("在线 \(online.episodes.count) / 20 集 · \(podcastSize(online.totalBytes))").font(.headline)}else{Text("尚未读取服务器列表").font(.headline)};if let date = store.onlineUpdated {Text("上次成功刷新：\(date.formatted(date:.abbreviated,time:.standard))").font(.caption).foregroundStyle(.secondary)}};Spacer();Button("刷新在线列表"){Task{await store.refreshOnline()}}.disabled(store.busy);Button("复制 RSS"){if let url = store.online?.rss_url {NSPasteboard.general.clearContents();NSPasteboard.general.setString(url,forType:.string)}}.disabled(store.online == nil)}
   if !store.onlineError.isEmpty {Label("读取失败：\(store.onlineError)\n\(store.online == nil ? "未获得在线状态，请检查连接后重试。" : "以下为上次成功读取的列表。")",systemImage:"exclamationmark.triangle").foregroundStyle(.orange).textSelection(.enabled)}
   if let online = store.online {
    if online.episodes.isEmpty {ContentUnavailableView("在线暂无节目",systemImage:"antenna.radiowaves.left.and.right",description:Text("在音频库选择已生成音频的文章，通过发布预览手动上传。"))}
    else {Table(online.episodes,selection:$store.onlineSelection) {TableColumn("标题",value:\.title);TableColumn("公众号"){Text($0.account ?? "—")};TableColumn("大小"){Text(podcastSize($0.audio_bytes ?? 0))};TableColumn("日期"){Text($0.published_at.map{String($0.prefix(10))} ?? "—")}}}
    HStack {Text(online.rss_url).font(.caption).textSelection(.enabled);Spacer();Button("下架所选…"){store.prepareRemoval()}.disabled(store.busy || store.onlineSelection.isEmpty)}
   } else {Spacer();Text("刷新后才会显示在线节目。网络不可用时，未知状态不会显示为 0 集。").foregroundStyle(.secondary);Spacer()}
  }.padding().navigationTitle("在线播客")
 }
}
