import Foundation

/// Each request is a separate process. Two readers drain both pipes concurrently.
final class PodcastBridge: @unchecked Sendable {
 private let lock = NSLock()
 private var process: Process?
 private func setProcess(_ value: Process?) {lock.withLock {process = value}}
 func cancel() {let p = lock.withLock {process};if p?.isRunning == true {p?.terminate()}}
 func request<T: Decodable>(_ action: String, python: String, fields: [String:Any] = [:]) async throws -> T {
  let root = FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("Wechat2Podcast/Podcast")
  var request = fields
  request["action"] = action;request["library"] = root.appendingPathComponent("library").path;request["config"] = root.appendingPathComponent("publish.json").path
  let input = try JSONSerialization.data(withJSONObject:request)
  let output: Data = try await Task.detached { [self] in
   let executable = (python as NSString).expandingTildeInPath
   guard executable.hasPrefix("/"),FileManager.default.isExecutableFile(atPath:executable) else {throw APIError(code:0,message:"找不到可执行的 Python：\(executable)。请在播客设置中指定已安装的 Python 3 路径。")}
   let p = Process();p.executableURL = URL(fileURLWithPath:executable);p.arguments = ["-m","wechat2podcast.gui"]
   let bundled = Bundle.main.resourceURL?.appendingPathComponent("python")
   let development = URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
   if let bundled,FileManager.default.fileExists(atPath:bundled.appendingPathComponent("wechat2podcast/gui.py").path) {p.currentDirectoryURL = bundled}
   else if FileManager.default.fileExists(atPath:development.appendingPathComponent("wechat2podcast/gui.py").path) {p.currentDirectoryURL = development}
   else {throw APIError(code:0,message:"找不到应用内的 Python 播客组件，请重新构建应用") }
   var env = ProcessInfo.processInfo.environment;env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + (env["PATH"] ?? "");p.environment = env
   let stdin = Pipe(),stdout = Pipe(),stderr = Pipe();p.standardInput = stdin;p.standardOutput = stdout;p.standardError = stderr
   setProcess(p)
   defer {setProcess(nil)}
   try p.run()
   let out = Task.detached {stdout.fileHandleForReading.readDataToEndOfFile()}
   let err = Task.detached {stderr.fileHandleForReading.readDataToEndOfFile()}
   try stdin.fileHandleForWriting.write(contentsOf:input);try stdin.fileHandleForWriting.close()
   p.waitUntilExit()
   let data = await out.value;let diagnostic = await err.value
   guard p.terminationStatus == 0 else {throw APIError(code:Int(p.terminationStatus),message:String(data:diagnostic,encoding:.utf8)?.trimmingCharacters(in:.whitespacesAndNewlines).nonEmpty ?? "操作已中止或 Python 执行失败")}
   return data
  }.value
  do {return try JSONDecoder().decode(T.self,from:output)} catch {throw APIError(code:0,message:"Python 返回格式无法读取：\(error.localizedDescription)")}
 }
}
private extension String {var nonEmpty: String? {isEmpty ? nil : self}}
