import Foundation

/// Read-only native Process -> Python smoke test. Add --online to query saved SSH profile.
@main enum NativePodcastSmoke {
 static func main() async throws {
  let bridge = PodcastBridge()
  let python = ProcessInfo.processInfo.environment["PODCAST_PYTHON"] ?? "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
  let local: PodcastDashboard = try await bridge.request("dashboard",python:python)
  print("Native dashboard: \(local.articles.count) articles, \(local.articles.filter{$0.canPlay}.count) ready")
  let deps: PodcastMessage = try await bridge.request("dependencies",python:python,fields:["voice":"Tingting"])
  print(deps.message)
  if CommandLine.arguments.contains("--inbox") {
   let pulled: PodcastPullResult = try await bridge.request("pull_scripts",python:python)
   print("Native inbox: \(pulled.downloaded) downloaded, \(pulled.imported) imported, \(pulled.test_count) tests")
   if let article = pulled.articles.first(where:{$0.sourceKind == "grok"}) {
    let detail: PodcastArticleDetail = try await bridge.request("article_detail",python:python,fields:["id":article.id])
    print("Native script detail: text \(detail.text.count) characters, notes \(detail.notes.count), test \(detail.is_test == true)")
   }
  }
  if CommandLine.arguments.contains("--online") {
   let online: PodcastOnline = try await bridge.request("online",python:python)
   print("Native SSH catalogue: \(online.episodes.count)/20, \(online.totalBytes) bytes")
   for article in local.articles {print(article.id+" "+article.serverStatus(episodes:online.episodes,refreshFailed:false))}
  }
 }
}
