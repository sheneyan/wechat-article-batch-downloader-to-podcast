import SwiftUI

struct PodcastView: View {
 @ObservedObject var store: PodcastStore
 var body: some View {
  VStack(spacing:0) {
   HStack {TextField("搜索标题、来源或日期",text:$store.query).textFieldStyle(.roundedBorder);Button("扫描归档"){Task{await store.scan()}}.disabled(store.busy);Button("拉取口播稿"){Task{await store.pullScripts()}}.disabled(store.busy)}.padding()
   HStack {Picker("来源",selection:$store.sourceFilter){ForEach(PodcastSourceFilter.allCases){Text($0.label).tag($0)}}.pickerStyle(.segmented).frame(width:300);Spacer();Toggle("显示测试稿",isOn:$store.showTests).toggleStyle(.checkbox)}.padding(.horizontal).padding(.bottom,10)
   Table(store.visible,selection:$store.selected) {
    TableColumn("标题"){article in HStack {Text(article.title);if article.isTest {Text("测试稿").font(.caption).foregroundStyle(.orange)}}}.width(min:240)
    TableColumn("来源",value:\.sourceLabel).width(min:100)
    TableColumn("文章日期"){Text($0.displayDate)}.width(130)
    TableColumn("本地音频"){Text($0.local_state.label)}.width(100)
    TableColumn("服务器"){Text($0.serverStatus(episodes:store.online?.episodes,refreshFailed:!store.onlineError.isEmpty))}.width(100)
   }
   HStack {
    Text("\(store.visible.count) 篇 · 已选 \(store.selectedArticles.count)").foregroundStyle(.secondary)
    Spacer()
    Button("查看稿件"){Task{await store.showDetail()}}.disabled(store.busy || store.selectedArticles.count != 1)
    Button("试听片段"){Task{await store.render(preview:true)}}.disabled(store.busy || store.selectedArticles.count != 1 || !store.canRenderSelection)
    Button("生成音频"){Task{await store.render()}}.disabled(store.busy || !store.canRenderSelection)
    Button("播放"){store.playSelected()}.disabled(store.selectedArticles.count != 1 || store.selectedArticles.first?.canPlay != true)
    Button("在 Finder 显示"){store.reveal()}.disabled(store.selectedArticles.isEmpty)
    Button("发布预览…"){Task{await store.preparePublish()}}.disabled(store.busy || !store.canPublishSelection)
   }.padding()
   Text("音频保存在本机。生成完成后，选择文章并查看发布预览，确认后才会上传。在线状态以最近一次刷新为准。").font(.caption).foregroundStyle(.secondary).padding(.horizontal).padding(.bottom,10)
  }.navigationTitle("音频库")
   .sheet(item:$store.detail){detail in PodcastArticleDetailView(detail:detail)}
 }
}
struct PodcastActivityView: View {
 @ObservedObject var store: PodcastStore
 var body: some View {
  VStack(alignment:.leading,spacing:8) {
   if !store.playingTitle.isEmpty {HStack {Button(store.playing ? "暂停" : "继续播放"){store.togglePlayback()};Button("停止播放"){store.stopPlayback()};Text(store.playingTitle).lineLimit(1)}}
   HStack {if store.busy {ProgressView().controlSize(.small)};Text(store.progress).textSelection(.enabled);Spacer();if store.busy {Button("停止任务"){store.cancel()}}}
   if !store.publicationWarnings.isEmpty {
    HStack(alignment:.top) {Label(store.publicationWarnings.joined(separator:"\n"),systemImage:"exclamationmark.triangle").foregroundStyle(.orange).textSelection(.enabled).fixedSize(horizontal:false,vertical:true);Spacer();Button("已读"){store.publicationWarnings = []}}
   }
   if !store.error.isEmpty {Text(store.error).foregroundStyle(.red).textSelection(.enabled).lineLimit(6)}
  }.font(.callout).padding(12)
 }
}
struct PublicationPreviewView: View {
 @ObservedObject var store: PodcastStore
 let plan: PodcastPlan
 @Environment(\.dismiss) private var dismiss
 var body: some View {
  VStack(alignment:.leading,spacing:16) {
   Text(plan.isRemoval ? "确认下架节目" : "确认发布到在线播客").font(.title2.bold())
   Text("操作后共 \(plan.online.count) 集 · \(podcastSize(plan.total_bytes))。在线保留最多 20 集，本地文件始终保留。").foregroundStyle(.secondary)
   List {
    if !plan.incoming.isEmpty {Section("新增或更新 · \(plan.incoming.count)"){ForEach(plan.incoming){Text($0.title)}}}
    Section(plan.isRemoval ? "将下架 · \(plan.removed.count)" : "将从在线列表淘汰 · \(plan.removed.count)") {if plan.removed.isEmpty {Text("无").foregroundStyle(.secondary)};ForEach(plan.removed){Text($0.title)}}
   }
   Text("确认使用本次预览的服务器版本提交；如列表已变化，需要重新预览。").font(.caption).foregroundStyle(.secondary)
   HStack {Spacer();Button("取消"){dismiss()};Button(plan.isRemoval ? "确认下架" : "确认发布"){Task{await store.commit(plan)}}.buttonStyle(.borderedProminent).disabled(store.busy)}
  }.padding(24).frame(width:660,height:480)
 }
}

struct PodcastArticleDetailView: View {
 let detail: PodcastArticleDetail
 @Environment(\.dismiss) private var dismiss
 var body: some View {
  VStack(alignment:.leading,spacing:14) {
   HStack {Text(detail.title).font(.title2.bold());if detail.is_test == true {Text("测试稿").foregroundStyle(.orange)};Spacer();Button("关闭"){dismiss()}}
   if detail.is_test == true {Text("测试稿仅供查看，不能试听、生成音频或发布。").foregroundStyle(.orange)}
   Text("实际朗读正文").font(.headline)
   ScrollView {Text(detail.text).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(12)}.background(.quaternary.opacity(0.3))
   Text("备注（不参与朗读）").font(.headline)
   ScrollView {Text(detail.notes.isEmpty ? "无备注" : detail.notes).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(12)}.frame(height:120).background(.quaternary.opacity(0.3))
  }.padding(24).frame(width:760,height:650)
 }
}
