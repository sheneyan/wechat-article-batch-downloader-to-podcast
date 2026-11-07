import AppKit
import AVFoundation
import Foundation

@MainActor final class PodcastStore: NSObject, ObservableObject, AVAudioPlayerDelegate {
 @Published var articles: [PodcastArticle] = []
 @Published var selected = Set<String>()
 @Published var query = "" {didSet{selected = []}}
 @Published var sourceFilter: PodcastSourceFilter = .all {didSet{selected = []}}
 @Published var showTests = false {didSet{selected = []}}
 @Published var detail: PodcastArticleDetail?
 @Published var voices: [PodcastVoice] = []
 @Published var inboxSettings = InboxSettings()
 @Published var inboxConfigLoaded = false
 @Published var online: PodcastOnline?
 @Published var onlineUpdated: Date?
 @Published var onlineError = ""
 @Published var onlineSelection = Set<String>()
 @Published var plan: PodcastPlan?
 @Published var busy = false
 @Published var progress = ""
 @Published var publicationWarnings: [String] = []
 @Published var error = ""
 @Published var settings = PublisherSettings()
 @Published var configLoaded = false
 @Published var archive: String = UserDefaults.standard.string(forKey:"podcastArchive") ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Documents/wechat_archived").path {didSet{UserDefaults.standard.set(archive,forKey:"podcastArchive");UserDefaults.standard.set(archive,forKey:"downloadDirectory")}}
 @Published var python: String = UserDefaults.standard.string(forKey:"podcastPython") ?? ["/Library/Frameworks/Python.framework/Versions/3.11/bin/python3","/opt/homebrew/bin/python3","/usr/local/bin/python3","/usr/bin/python3"].first{FileManager.default.isExecutableFile(atPath:$0)} ?? "/opt/homebrew/bin/python3" {didSet{UserDefaults.standard.set(python,forKey:"podcastPython")}}
 @Published var voice: String = UserDefaults.standard.string(forKey:"podcastVoice") ?? "Tingting" {didSet{UserDefaults.standard.set(voice,forKey:"podcastVoice")}}
 @Published var rate: Int = UserDefaults.standard.integer(forKey:"podcastRate") == 0 ? 180 : UserDefaults.standard.integer(forKey:"podcastRate") {didSet{UserDefaults.standard.set(rate,forKey:"podcastRate")}}
 @Published var playing = false
 @Published var playingTitle = ""
 private var player: AVAudioPlayer?
 private let bridge = PodcastBridge()
 private var cancelled = false
 private var initialized = false
 var visible: [PodcastArticle] {articles.filter{$0.isVisible(source:sourceFilter,showTests:showTests,query:query)}}
 var selectedArticles: [PodcastArticle] {visible.filter{selected.contains($0.id)}}
 var canRenderSelection: Bool {!selectedArticles.isEmpty && selectedArticles.allSatisfy{!$0.isTest}}
 var canPublishSelection: Bool {canRenderSelection && selectedArticles.allSatisfy(\.canPlay)}
 var onlineIDs: Set<String> {Set(online?.episodes.map(\.id) ?? [])}
 func request<T: Decodable>(_ action: String,_ fields: [String:Any] = [:]) async throws -> T {try await bridge.request(action,python:python,fields:fields)}
 func work(_ message: String, operation: () async throws -> Void) async {
  guard !busy else{return};busy = true;cancelled = false;progress = message;error = ""
  defer {busy = false}
  do {try await operation();if cancelled {progress = "任务已停止"}} catch {self.error = error.localizedDescription;progress = "操作未完成"}
 }
 func initialize() async {guard !initialized else{return};initialized = true;await scan(indexOnly:true);await loadSettings();await loadInboxSettings()}
 func scan(indexOnly: Bool = false) async {
  await work("正在扫描本地文章") {let result: PodcastDashboard = try await request(indexOnly ? "dashboard" : "scan",["archive":(archive as NSString).expandingTildeInPath]);articles = result.articles;progress = "已载入 \(articles.count) 篇文章"}
 }
 func pullScripts() async {
  await work("正在拉取口播稿") {let result: PodcastPullResult = try await request("pull_scripts");articles = result.articles;selected = [];progress = "已下载 \(result.downloaded) 份 · 导入 \(result.imported) 篇 · 测试稿 \(result.test_count) 篇（默认隐藏）"}
 }
 func loadInboxSettings() async {await work("正在读取口播稿收件配置") {inboxSettings = try await request("inbox_config");inboxConfigLoaded = true;progress = "口播稿收件配置已读取；点击拉取时才连接服务器"}}
 func saveInboxSettings() async {await work("正在保存口播稿收件配置") {let data = try JSONEncoder().encode(inboxSettings);let fields = try JSONSerialization.jsonObject(with:data);inboxSettings = try await request("save_inbox_config",["settings":fields]);inboxConfigLoaded = true;progress = "口播稿收件配置已保存"}}
 func testInbox() async {await work("正在测试口播稿收件连接") {let result: PodcastMessage = try await request("test_inbox");progress = result.message}}
 func showDetail() async {guard selectedArticles.count == 1,let article = selectedArticles.first else{return};await work("正在读取稿件") {detail = try await request("article_detail",["id":article.id]);progress = "稿件已读取"}}
 func loadSettings() async {await work("正在读取发布配置") {settings = try await request("config");configLoaded = true;progress = "发布采用手动操作"}}
 func saveSettings() async {await work("正在保存配置") {let data = try JSONEncoder().encode(settings);let fields = try JSONSerialization.jsonObject(with:data);settings = try await request("save_config",["settings":fields]);configLoaded = true;invalidateOnline();progress = "配置已保存；请重新刷新在线列表"}}
 func invalidateOnline() {online = nil;onlineUpdated = nil;onlineSelection = [];plan = nil;onlineError = ""}
 func checkDependencies() async {await work("正在检查本机环境") {let result: PodcastMessage = try await request("dependencies",["voice":voice]);progress = result.message}}
 func loadVoices() async {await work("正在读取本机音色") {let result: PodcastVoices = try await request("voices");voices = result.voices;progress = "本机音色已读取"}}
 var playingVoicePreview: Bool {playing && playingTitle == "音色试听"}
 func previewVoice() async {
  guard !busy else{return}
  let selectedVoice = voice,selectedRate = rate
  await work("正在生成音色试听") {
   stopPlayback()
   let audio: PodcastAudio = try await request("voice_preview",["voice":selectedVoice,"rate":selectedRate])
   if !cancelled {try play(path:audio.audio_path,title:"音色试听");progress = "音色试听 · \(selectedVoice) · 语速 \(selectedRate)"}
  }
 }
 var selectableVoices: [PodcastVoice] {
  var result = voices.filter{$0.language.hasPrefix("zh") || $0.id == voice}
  if !result.contains(where:{$0.id == voice}) {result.insert(PodcastVoice(id:voice,language:"当前设置"),at:0)}
  return result
 }
 func deleteArticles(_ ids: [String]) async {
  guard !busy,!ids.isEmpty else{return}
  await work("正在删除本地文章与音频") {
   stopPlayback()
   let result: PodcastDashboard = try await request("delete_articles",["ids":ids]);articles = result.articles
   selected.subtract(ids);detail = nil;plan = nil
   progress = "已删除 \(ids.count) 篇本地文章与音频，后续扫描和拉取不再导入；线上节目未改动"
  }
 }
 func connection(deploy: Bool = false) async {await work(deploy ? "正在部署发布组件" : "正在测试 SSH") {let result: PodcastMessage = try await request(deploy ? "deploy" : "test_connection");progress = result.message}}
 func refreshOnline() async {
  await work("正在读取服务器节目列表") {do {let result: PodcastOnline = try await request("online");online = result;onlineSelection.formIntersection(Set(result.episodes.map(\.id)));onlineUpdated = Date();onlineError = "";progress = "在线列表已刷新"} catch {onlineError = error.localizedDescription;throw error}}
 }
 func render(preview: Bool = false) async {
  guard canRenderSelection else{error = "请选择非测试稿件；测试稿不能试听或生成音频";return}
  let items = selectedArticles
  await work(preview ? "正在生成试听" : "正在生成音频") {
   for (index,item) in items.enumerated() {
    if cancelled {break};progress = "\(preview ? "试听" : "生成") \(index+1)/\(items.count) · \(item.title)"
    let audio: PodcastAudio = try await request(preview ? "preview" : "render",["id":item.id,"voice":voice,"rate":rate,"characters":260])
    if preview && !cancelled {try play(path:audio.audio_path,title:item.title);break}
   }
   let result: PodcastDashboard = try await request("dashboard");articles = result.articles
   progress = cancelled ? "已停止；完成的音频已保留" : "音频处理完成"
  }
 }
 func play(path: String,title: String) throws {player?.stop();player = try AVAudioPlayer(contentsOf:URL(fileURLWithPath:path));player?.delegate = self;playing = player?.play() ?? false;playingTitle = title}
 func playSelected() {guard let item = selectedArticles.first,item.canPlay,let path = item.audio_path else{return};do{try play(path:path,title:item.title)}catch{self.error = error.localizedDescription}}
 nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {Task { @MainActor [weak self] in self?.playing = false }}
 func togglePlayback() {if playing {player?.pause();playing = false}else{playing = player?.play() ?? false}}
 func stopPlayback() {player?.stop();player = nil;playing = false;playingTitle = ""}
 func cancel() {cancelled = true;bridge.cancel()}
 func reveal() {NSWorkspace.shared.activateFileViewerSelecting(selectedArticles.map{URL(fileURLWithPath:$0.audio_path ?? $0.source_path)})}
 func preparePublish() async {
  guard canPublishSelection else{error = "请选择已生成音频的非测试稿件";return}
  let ids = selectedArticles.map(\.id)
  await work("正在预览发布变化") {var result: PodcastPlan = try await request("plan",["ids":ids]);result.selectedIDs = ids;plan = result;progress = "请检查新节目及淘汰列表，再确认发布"}
 }
 func prepareRemoval() {
  guard let online else{return};let removed = online.episodes.filter{onlineSelection.contains($0.id)};guard !removed.isEmpty else{return}
  plan = PodcastPlan(revision:online.revision,incoming:[],removed:removed,online:online.episodes.filter{!onlineSelection.contains($0.id)},total_bytes:online.totalBytes - removed.reduce(0){$0 + ($1.audio_bytes ?? 0)},isRemoval:true,selectedIDs:removed.map(\.id))
 }
 func recordPublicationWarnings(_ warnings: [String]) {
  for warning in warnings where !warning.isEmpty && !publicationWarnings.contains(warning) {publicationWarnings.append(warning)}
 }
 func commit(_ preview: PodcastPlan) async {
  plan = nil
  await work(preview.isRemoval ? "正在下架节目" : "正在发布节目") {
   let result: PodcastCommit = try await request(preview.isRemoval ? "unpublish" : "publish",["ids":preview.selectedIDs,"revision":preview.revision])
   // Keep the last known RSS URL while replacing the committed revision and episode list.
   if let old = online {online = PodcastOnline(revision:result.revision,episodes:result.episodes,rss_url:old.rss_url);onlineUpdated = Date()}
   recordPublicationWarnings(result.warnings ?? [])
   progress = "服务器操作完成；本地文件已保留"
  }
  if error.isEmpty {await refreshOnline()}
 }
}
