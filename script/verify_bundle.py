#!/usr/bin/env python3
"""Run after exercising the app to catch writes into signed resources."""
import argparse
import subprocess
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('app',type=Path)
args=parser.parse_args()
app=args.app.expanduser().resolve()
subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
if list((app/'Contents/Resources/python').rglob('__pycache__')):
    raise SystemExit('App 包内出现 Python 缓存，请使用 -B 并清理后重新签名')
print('运行后的 App 签名有效，包内没有 Python 字节码缓存。')
