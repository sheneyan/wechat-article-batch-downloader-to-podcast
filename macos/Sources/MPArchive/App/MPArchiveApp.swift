import AppKit
import SwiftUI

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
 static weak var backend: Backend?
 static weak var podcast: PodcastStore?
 static weak var library: Library?
 private var ending = false
 func applicationDidFinishLaunching(_ notification: Notification) {
  NSApp.setActivationPolicy(.regular)
  NSApp.activate(ignoringOtherApps: true)
 }
 func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
  if ending {return .terminateNow}
  let activeDownloads = Self.library?.tasks.contains { ["running","pending","queued"].contains($0.status) } ?? false
  if Self.podcast?.busy == true || Self.backend?.busy == true || Self.library?.scanBusy == true || Self.library?.queueing == true || activeDownloads {
   let alert = NSAlert();alert.messageText = "仍有任务正在运行";alert.informativeText = "关闭窗口可以继续任务。现在退出会停止当前处理，已完成的本地文件会保留；发布中止后请刷新在线状态确认结果。";alert.addButton(withTitle:"继续等待");alert.addButton(withTitle:"停止任务并退出")
   if alert.runModal() != .alertSecondButtonReturn {return .terminateCancel}
   Self.podcast?.cancel()
  }
  ending = true
  Task {
   while Self.podcast?.busy == true || Self.backend?.busy == true {try? await Task.sleep(for:.milliseconds(100))}
   await Self.backend?.stop();sender.reply(toApplicationShouldTerminate: true)
  }
  return .terminateLater
 }
 func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {false}
}
@main struct MPArchiveApp: App {
 @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
 @StateObject private var backend = Backend()
 @StateObject private var library = Library()
 @StateObject private var podcast = PodcastStore()
 var body: some Scene {
  WindowGroup("微信文章播客", id: "main") {
   ContentView(backend: backend, library: library, podcast:podcast)
    .frame(minWidth: 960, minHeight: 640)
    .task {AppDelegate.backend = backend;AppDelegate.podcast = podcast;AppDelegate.library = library;if !backend.running && !backend.busy {await backend.launch()};library.begin(backend);await podcast.initialize()}
  }.defaultSize(width: 1180, height: 780)
   .commands {
    CommandGroup(replacing: .newItem) {}
    CommandMenu("文章库") {
     Button("刷新公众号") {Task{await library.refresh()}}.keyboardShortcut("r")
     Button("下载所选文章") {Task{await library.enqueue(selectedOnly: true)}}.keyboardShortcut("d").disabled(library.selectedArticles.isEmpty)
     Button("打开导出目录") {NSWorkspace.shared.open(backend.downloads)}.keyboardShortcut("o",modifiers:[.command,.shift])
    }
   }
  Settings {TabView {PodcastSettingsView(store:podcast).tabItem{Label("播客",systemImage:"waveform")};SettingsView(backend: backend,library:library).tabItem{Label("下载与微信",systemImage:"arrow.down.circle")}}.frame(width:760,height:680)}
 }
}
