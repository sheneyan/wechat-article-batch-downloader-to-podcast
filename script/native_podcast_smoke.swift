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
  if CommandLine.arguments.contains("--online") {
   let online: PodcastOnline = try await bridge.request("online",python:python)
   print("Native SSH catalogue: \(online.episodes.count)/20, \(online.totalBytes) bytes")
   for article in local.articles {print(article.id+" "+article.serverStatus(episodes:online.episodes,refreshFailed:false))}
  }
 }
}
