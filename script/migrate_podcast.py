#!/usr/bin/env python3
"""Copy the initial CLI library/profile to the Mac app without overwriting existing data."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = Path.home()/'Library/Application Support/Wechat2Podcast/Podcast'


def main():
    DEST.mkdir(parents=True, exist_ok=True, mode=0o700)
    copied = 0
    source = ROOT/'.local/library'
    if source.is_dir():
        for folder in source.iterdir():
            dest = DEST/'library'/folder.name
            if folder.is_dir() and not dest.exists():
                dest.parent.mkdir(exist_ok=True)
                shutil.copytree(folder,dest)
                copied += 1
    profile = ROOT/'.private/publish.json'
    dest_profile = DEST/'publish.json'
    if profile.exists() and not dest_profile.exists():
        shutil.copy2(profile,dest_profile)
        dest_profile.chmod(0o600)
    inbox_profile=ROOT/'.private/inbox-reader.json'
    dest_inbox=DEST/'inbox-reader.json'
    if inbox_profile.exists() and not dest_inbox.exists():
        shutil.copy2(inbox_profile,dest_inbox)
        dest_inbox.chmod(0o600)
    print(json.dumps({'copied_articles':copied,'destination':str(DEST)},ensure_ascii=False))


if __name__ == '__main__':
    main()
