#!/usr/bin/env bash
# Compatibility entry point for the integrated app in this fork.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-run}" in
 --build-only) exec "$PROJECT_DIR/script/build_app.sh" --build-only ;;
 --install|--verify|run) exec "$PROJECT_DIR/script/build_app.sh" --install ;;
 *) echo "usage: $0 [--build-only|--install|--verify] (quit 微信文章播客 before installing updates)" >&2; exit 2 ;;
esac
