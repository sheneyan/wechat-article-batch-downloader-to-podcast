import Foundation

enum AudioReadiness: String, Codable {
 case ready, stale, missing
 var label: String {switch self {case .ready: return "已生成";case .stale: return "正文已更新";case .missing: return "未生成"}}
}
enum PodcastSourceFilter: String, CaseIterable, Identifiable {
 case all, wechat, grok
 var id: String {rawValue}
 var label: String {switch self {case .all:return "全部";case .wechat:return "公众号";case .grok:return "每日X"}}
}
struct InboxSettings: Codable {var base_url = "";var read_token = ""}
struct PodcastArticleDetail: Decodable, Identifiable {
 let id: String
 let title: String
 let text: String
 let notes: String
 let source_kind: String?
 let is_test: Bool?
}
struct PodcastPullResult: Decodable {
 let articles: [PodcastArticle]
 let library: String
 let downloaded: Int
 let imported: Int
 let test_count: Int
}
struct PodcastArticle: Decodable, Identifiable {
 let id: String
 let title: String
 let account: String
 let author: String?
 let published_at: String?
 let source_url: String?
 let source_path: String
 let source_kind: String?
 let source_id: String?
 let is_test: Bool?
 let local_state: AudioReadiness
 let audio_path: String?
 let duration: Double?
 let audio_bytes: Int64?
 let audio_sha256: String?
 var displayDate: String {guard let published_at,!published_at.isEmpty else{return "日期未知"};return String(published_at.prefix(10))}
 func serverStatus(episodes: [PodcastEpisode]?, refreshFailed: Bool) -> String {
  guard !refreshFailed else{return "待刷新"}
  guard let episodes else{return "未查询"}
  guard let episode = episodes.first(where:{$0.id == id}) else{return "未发布"}
  if local_state == .stale {return "本地待转换"}
  guard local_state == .ready, let localHash = audio_sha256,let remoteHash = episode.audio_sha256 else{return "待核对"}
  return localHash == remoteHash ? "在线" : "待更新"
 }
 var isTest: Bool {is_test ?? false}
 var sourceKind: String {source_kind ?? "wechat"}
 var sourceLabel: String {sourceKind == "grok" ? "每日X" : account}
 func isVisible(source: PodcastSourceFilter, showTests: Bool, query: String) -> Bool {
  (!isTest || showTests) && (source == .all || source.rawValue == sourceKind) && matches(query)
 }
 var canPlay: Bool {!isTest && local_state == .ready && audio_path != nil}
 func matches(_ query: String) -> Bool {query.isEmpty || [title,account,author ?? "",published_at ?? ""].contains{$0.localizedCaseInsensitiveContains(query)}}
}
struct PodcastEpisode: Decodable, Identifiable {
 let id: String
 let title: String
 let account: String?
 let author: String?
 let published_at: String?
 let audio_bytes: Int64?
 let audio_sha256: String?
 let duration: Double?
}
struct PodcastDashboard: Decodable {let articles: [PodcastArticle];let library: String}
struct PodcastOnline: Decodable {
 let revision: String
 let episodes: [PodcastEpisode]
 let rss_url: String
 var totalBytes: Int64 {episodes.reduce(0){$0 + ($1.audio_bytes ?? 0)}}
}
struct PodcastPlan: Decodable, Identifiable {
 var id: String {revision + (isRemoval ? "remove" : "publish")}
 let revision: String
 let incoming: [PodcastEpisode]
 let removed: [PodcastEpisode]
 let online: [PodcastEpisode]
 let total_bytes: Int64
 var isRemoval = false
 var selectedIDs: [String] = []
 enum CodingKeys: String,CodingKey {case revision,incoming,removed,online,total_bytes}
}
struct PodcastAudio: Decodable {let audio_path: String;let duration: Double?}
struct PodcastMessage: Decodable {let message: String}
struct PodcastCommit: Decodable {let revision: String;let episodes: [PodcastEpisode];let removed: [PodcastEpisode];let warnings: [String]?}
struct PublisherSettings: Codable {
 var feed_title = "我的订阅"
 var ssh_host = ""
 var ssh_user = "root"
 var ssh_port = 22
 var identity_file = ""
 var remote_root = "/opt/wechat2podcast"
 var base_url = ""
}
func podcastSize(_ bytes: Int64) -> String {ByteCountFormatter.string(fromByteCount:bytes,countStyle:.file)}
