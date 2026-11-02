#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
MODE="${1:---build-only}"
BUNDLE="$PROJECT_DIR/dist/微信文章播客.app"
if [[ "$MODE" != "--build-only" && "$MODE" != "--install" ]]; then
  echo "Usage: $0 [--build-only|--install]" >&2
  exit 2
fi
if [[ "$MODE" == "--install" ]] && pgrep -f "$HOME/Applications/微信文章播客.app/Contents/MacOS/MPArchive" >/dev/null; then
  echo "请先退出正在运行的“微信文章播客”，再安装更新；原公众号文章下载器不受影响。" >&2
  exit 1
fi
"$PROJECT_DIR/build-downloader.sh"
swift build --package-path "$PROJECT_DIR/macos"
BUILD_DIR="$(swift build --package-path "$PROJECT_DIR/macos" --show-bin-path)"
mkdir -p "$BUNDLE/Contents/MacOS" "$BUNDLE/Contents/Resources/python/wechat2podcast"
cp "$BUILD_DIR/MPArchive" "$BUNDLE/Contents/MacOS/MPArchive"
cp "$PROJECT_DIR/mp_article_downloader_src/mp_article_batch_downloader" "$BUNDLE/Contents/Resources/mp_article_batch_downloader"
cp "$PROJECT_DIR/wechat2podcast/"*.py "$BUNDLE/Contents/Resources/python/wechat2podcast/"
cp "$PROJECT_DIR/LICENSE" "$BUNDLE/Contents/Resources/LICENSE"
cp "$PROJECT_DIR/third_party/UPSTREAM.md" "$BUNDLE/Contents/Resources/UPSTREAM.md"
if [[ -f "$PROJECT_DIR/macos/AppIcon.icns" ]]; then
  cp "$PROJECT_DIR/macos/AppIcon.icns" "$BUNDLE/Contents/Resources/AppIcon.icns"
fi
cat > "$BUNDLE/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>MPArchive</string>
<key>CFBundleIdentifier</key><string>io.zi5.wechat2podcast</string>
<key>CFBundleName</key><string>微信文章播客</string>
<key>CFBundleDisplayName</key><string>微信文章播客</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>NSHighResolutionCapable</key><true/>
<key>CFBundleDevelopmentRegion</key><string>zh_CN</string>
<key>CFBundleLocalizations</key><array><string>zh_CN</string></array>
<key>MPArchiveChannel</key><string>个人开发版</string>
</dict></plist>
PLIST
SIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
if [[ -z "$SIGN_IDENTITY" ]]; then
  SIGN_IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null | sed -n 's/.*"\(Apple Development:[^"]*\)".*/\1/p' | head -n 1)"
fi
[[ -n "$SIGN_IDENTITY" ]] || SIGN_IDENTITY="-"
codesign --force --sign "$SIGN_IDENTITY" "$BUNDLE/Contents/Resources/mp_article_batch_downloader"
codesign --force --sign "$SIGN_IDENTITY" "$BUNDLE"
if [[ "$MODE" == "--install" ]]; then
  python3 "$PROJECT_DIR/script/migrate_podcast.py"
  mkdir -p "$HOME/Applications"
  ditto "$BUNDLE" "$HOME/Applications/微信文章播客.app"
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$HOME/Applications/微信文章播客.app"
  open "$HOME/Applications/微信文章播客.app"
fi
echo "App built: $BUNDLE"
