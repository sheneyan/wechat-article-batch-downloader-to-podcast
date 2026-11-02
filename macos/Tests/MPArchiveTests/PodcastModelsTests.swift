import XCTest
@testable import MPArchive
final class PodcastModelsTests: XCTestCase {
 func testReadinessDoesNotConfuseOnlineWithLocalAudio() throws {
  let json = #"{"id":"a","title":"文章","account":"公众号","published_at":"2026-11-02T08:00:00+08:00","source_path":"/tmp/a.md","local_state":"stale","audio_path":"/tmp/a.m4a"}"#
  let article = try JSONDecoder().decode(PodcastArticle.self,from:Data(json.utf8))
  XCTAssertFalse(article.canPlay)
  XCTAssertEqual(article.local_state.label,"正文已更新")
  XCTAssertTrue(article.matches("公众号"))
  XCTAssertTrue(article.matches("2026-11"))
  XCTAssertFalse(article.matches("missing"))
 }
 func testReadyRequiresAudioPath() throws {
  let article = try JSONDecoder().decode(PodcastArticle.self,from:Data(#"{"id":"a","title":"A","account":"B","source_path":"/tmp/a","local_state":"ready"}"#.utf8))
  XCTAssertFalse(article.canPlay)
  XCTAssertEqual(article.displayDate,"日期未知")
 }
 func testPreviewPreservesServerRevisionAndEvictionList() throws {
  let json = #"{"revision":"rev-1","incoming":[{"id":"new","title":"New","audio_bytes":100}],"removed":[{"id":"old","title":"Old","audio_bytes":200}],"online":[{"id":"new","title":"New","audio_bytes":100}],"total_bytes":100}"#
  let plan = try JSONDecoder().decode(PodcastPlan.self,from:Data(json.utf8))
  XCTAssertEqual(plan.revision,"rev-1")
  XCTAssertEqual(plan.removed.map(\.id),["old"])
  XCTAssertFalse(plan.isRemoval)
 }
 func testOnlineBytesCalculatedFromActualEpisodes() throws {
  let online = try JSONDecoder().decode(PodcastOnline.self,from:Data(#"{"revision":"r","episodes":[{"id":"a","title":"A","audio_bytes":123},{"id":"b","title":"B","audio_bytes":456}],"rss_url":"https://example.org/feed.xml"}"#.utf8))
  XCTAssertEqual(online.totalBytes,579)
 }
 func testServerStatusRequiresSuccessfulRefreshAndMatchingHash() throws {
  let article = try JSONDecoder().decode(PodcastArticle.self,from:Data(#"{"id":"a","title":"A","account":"B","source_path":"/tmp/a","local_state":"ready","audio_path":"/tmp/audio.mp3","audio_sha256":"current","published_at":"2026-11-02T08:00:00+08:00"}"#.utf8))
  let same = try JSONDecoder().decode(PodcastEpisode.self,from:Data(#"{"id":"a","title":"A","audio_sha256":"current"}"#.utf8))
  let old = try JSONDecoder().decode(PodcastEpisode.self,from:Data(#"{"id":"a","title":"A","audio_sha256":"old"}"#.utf8))
  XCTAssertEqual(article.serverStatus(episodes:[same],refreshFailed:false),"在线")
  XCTAssertEqual(article.serverStatus(episodes:[old],refreshFailed:false),"待更新")
  XCTAssertEqual(article.serverStatus(episodes:[same],refreshFailed:true),"待刷新")
  XCTAssertEqual(article.serverStatus(episodes:[],refreshFailed:true),"待刷新")
  XCTAssertEqual(article.serverStatus(episodes:[],refreshFailed:false),"未发布")
  XCTAssertEqual(article.serverStatus(episodes:nil,refreshFailed:false),"未查询")
  XCTAssertEqual(article.displayDate,"2026-11-02")
 }
 func testStaleLocalContentDoesNotClaimMatchingOnlineAudio() throws {
  let article = try JSONDecoder().decode(PodcastArticle.self,from:Data(#"{"id":"a","title":"A","account":"B","source_path":"/tmp/a","local_state":"stale","audio_path":"/tmp/audio.mp3","audio_sha256":"old"}"#.utf8))
  let episode = try JSONDecoder().decode(PodcastEpisode.self,from:Data(#"{"id":"a","title":"A","audio_sha256":"old"}"#.utf8))
  XCTAssertEqual(article.serverStatus(episodes:[episode],refreshFailed:false),"本地待转换")
 }
 @MainActor func testInvalidatingEndpointClearsEveryOnlineSnapshot() throws {
  let store = PodcastStore()
  store.online = try JSONDecoder().decode(PodcastOnline.self,from:Data(#"{"revision":"r","episodes":[],"rss_url":"https://old.example/feed.xml"}"#.utf8))
  store.onlineUpdated = Date();store.onlineSelection = ["old"];store.onlineError = "unreachable"
  store.plan = PodcastPlan(revision:"r",incoming:[],removed:[],online:[],total_bytes:0)
  store.invalidateOnline()
  XCTAssertNil(store.online);XCTAssertNil(store.onlineUpdated);XCTAssertNil(store.plan)
  XCTAssertTrue(store.onlineSelection.isEmpty);XCTAssertTrue(store.onlineError.isEmpty)
 }

 @MainActor func testPublicationWarningsSurviveSuccessfulRefreshProgress() async {
  let store = PodcastStore()
  store.recordPublicationWarnings(["旧音频清理未完成"])
  await store.work("正在读取服务器节目列表") {store.progress = "在线列表已刷新"}
  XCTAssertEqual(store.progress,"在线列表已刷新")
  XCTAssertEqual(store.publicationWarnings,["旧音频清理未完成"])
  store.recordPublicationWarnings(["旧音频清理未完成","目录持久化未确认"])
  XCTAssertEqual(store.publicationWarnings,["旧音频清理未完成","目录持久化未确认"])
 }

}
