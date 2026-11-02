import Foundation

enum AudioReadiness: String, Codable {
 case ready, stale, missing
 var label: String {switch self {case .ready: return "已生成";case .stale: return "正文已更新";case .missing: return "未生成"}}
}
struct PodcastArticle: Decodable, Identifiable {
 let id: String
 let title: String
 let account: String
 let author: String?
 let published_at: String?
 let source_url: String?
 let source_path: String
 let local_state: AudioReadiness
 let audio_path: String?
 let duration: Double?
 let audio_bytes: Int64?
 let audio_sha256: String?
 var displayDate: String {published_at.map{String($0.prefix(10))} ?? "—"}
 func serverStatus(episodes: [PodcastEpisode]?, refreshFailed: Bool) -> String {
  guard !refreshFailed else{return "待刷新"}
  guard let episodes else{return "未查询"}
  guard let episode = episodes.first(where:{$0.id == id}) else{return "未发布"}
  if local_state == .stale {return "本地待转换"}
  guard local_state == .ready, let localHash = audio_sha256,let remoteHash = episode.audio_sha256 else{return "待核对"}
  return localHash == remoteHash ? "在线" : "待更新"
 }
 var canPlay: Bool {local_state == .ready && audio_path != nil}
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
 var ssh_host = ""
 var ssh_user = "root"
 var ssh_port = 22
 var identity_file = ""
 var remote_root = "/opt/wechat2podcast"
 var base_url = ""
}
func podcastSize(_ bytes: Int64) -> String {ByteCountFormatter.string(fromByteCount:bytes,countStyle:.file)}
