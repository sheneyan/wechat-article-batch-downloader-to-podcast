"""SSH-only publisher. No HTTP write endpoint or long-running process."""
import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from .core import make_rss, select_online


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


class Publisher:
    def __init__(self, root, base_url, token):
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', token):
            raise ValueError('无效节目路径')
        self.root = Path(root)
        self.base_url = base_url.rstrip('/')
        self.public = self.root/'www'/'wechat'/token
        self.root.mkdir(parents=True, exist_ok=True)
        self._check_identity()

    def _check_identity(self):
        if (self.root/'current').exists():
            feed = self.public/'feed.xml'
            target=feed.readlink() if feed.is_symlink() else None
            if target and not target.is_absolute():
                target=feed.parent/target
            # Check the stable pointer's parent, not its current generation;
            # a concurrent publication may swap current during this check.
            valid=(target is not None and target.name=='feed.xml' and target.parent.name=='current'
                   and target.parent.parent.resolve()==self.root.resolve())
            if not valid:
                raise ValueError('此服务器目录已有其他节目标识。请保留原 RSS 路径，或为新节目使用独立目录。')

    def _status(self):
        pointer = self.root/'current'
        if not pointer.exists():
            return dict(revision='0'*64, episodes=[])
        data = (pointer/'state.json').read_bytes()
        return dict(revision=hashlib.sha256(data).hexdigest(), episodes=json.loads(data))

    def status(self):
        with (self.root/'publish.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            return self._status()

    def prepare(self, batch):
        self._check_batch(batch)
        (self.root/'.staging'/batch).mkdir(parents=True, mode=0o700, exist_ok=False)

    @staticmethod
    def _check_batch(batch):
        if not re.fullmatch(r'[a-f0-9]{32}', batch):
            raise ValueError('无效上传批次')

    @staticmethod
    def _validate(ep):
        if not re.fullmatch(r'[a-f0-9]{20}', ep['id']):
            raise ValueError('无效文章 ID')
        if not re.fullmatch(r'[a-f0-9]{64}\.mp3', ep['audio_file']):
            raise ValueError('无效音频文件名')
        if ep['audio_file'] != ep['audio_sha256']+'.mp3':
            raise ValueError('文件名与校验和不一致')
        if not isinstance(ep['audio_bytes'], int) or ep['audio_bytes'] <= 0:
            raise ValueError('无效音频大小')
        if not isinstance(ep['duration'], (int, float)) or not math.isfinite(ep['duration']) or ep['duration'] <= 0:
            raise ValueError('无效音频时长')
        if datetime.fromisoformat(ep['published_at']).utcoffset() is None:
            raise ValueError('发布日期必须含时区')
        url = urlsplit(ep['source_url'])
        if url.scheme != 'https' or url.hostname != 'mp.weixin.qq.com':
            raise ValueError('无效原文地址')
        for field in ('title', 'account', 'author'):
            if not isinstance(ep[field], str):
                raise ValueError('无效元数据')
        # Validate XML before any active catalogue mutation.
        try:
            ET.fromstring(make_rss([ep], 'https://example.invalid'))
        except ET.ParseError as exc:
            raise ValueError('文章元数据含 XML 不支持的字符') from exc

    def remove(self, ids, expected_revision):
        if not ids:
            raise ValueError('请选择要下线的文章')
        return self.commit([], uuid.uuid4().hex, expected_revision, remove_ids=ids)

    def commit(self, incoming, batch, expected_revision, remove_ids=None):
        self._check_batch(batch)
        staging = self.root/'.staging'/batch
        audio = self.public/'audio'
        with (self.root/'publish.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._check_identity()
            current = self._status()
            if expected_revision != current['revision']:
                raise ValueError('在线目录已变化，请重新预览发布计划')
            for ep in incoming:
                self._validate(ep)
            if remove_ids is not None:
                known = {ep['id'] for ep in current['episodes']}
                if not set(remove_ids).issubset(known):
                    raise ValueError('下线文章不在当前目录中，请刷新后重试')
                online = [ep for ep in current['episodes'] if ep['id'] not in remove_ids]
                removed = [ep for ep in current['episodes'] if ep['id'] in remove_ids]
            else:
                online, removed = select_online(current['episodes'], incoming)
            audio.mkdir(parents=True, exist_ok=True)
            # Validate every file before moving any file into the public tree.
            sources = {}
            for ep in online:
                dest = audio/ep['audio_file']
                source = dest if dest.exists() else staging/ep['audio_file']
                if not source.is_file() or source.stat().st_size != ep['audio_bytes']:
                    raise ValueError('音频缺失或大小不符: '+ep['id'])
                if sha256_file(source) != ep['audio_sha256']:
                    raise ValueError('音频校验失败: '+ep['id'])
                sources[ep['audio_file']] = source
            generation = self.root/'generations'/uuid.uuid4().hex
            pointer = self.root/('current-'+uuid.uuid4().hex)
            moved = []
            try:
                for name, source in sources.items():
                    dest = audio/name
                    if source != dest:
                        os.replace(source, dest)
                        moved.append(dest)
                        dest.chmod(0o644)
                        with dest.open('rb') as stream:
                            os.fsync(stream.fileno())
                generation.mkdir(parents=True)
                state = json.dumps(online, ensure_ascii=False, sort_keys=True, indent=2).encode()
                for name, data in [('state.json', state), ('feed.xml', make_rss(online, self.base_url))]:
                    with (generation/name).open('wb') as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                feed = self.public/'feed.xml'
                if not feed.is_symlink():
                    feed.symlink_to(self.root/'current'/'feed.xml')
                pointer.symlink_to(generation)
                # RSS and state change together via a single atomic symlink swap.
                os.replace(pointer, self.root/'current')
            except Exception:
                for path in moved:
                    path.unlink(missing_ok=True)
                pointer.unlink(missing_ok=True)
                shutil.rmtree(generation, ignore_errors=True)
                raise
            warnings = []
            # The catalogue is committed. Report cleanup failures without claiming a rollback.
            try:
                directory_fd = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                keep = set(sources)
                for old in audio.glob('*.mp3'):
                    if old.name not in keep:
                        old.unlink()
                shutil.rmtree(staging, ignore_errors=True)
                for old in (self.root/'generations').iterdir():
                    # Let in-flight nginx symlink resolution finish before pruning tiny manifests.
                    if old != generation and old.stat().st_mtime < time.time()-3600:
                        shutil.rmtree(old)
                staging_root = self.root/'.staging'
                if staging_root.exists():
                    for old in staging_root.iterdir():
                        if old.is_dir() and old.stat().st_mtime < time.time()-86400:
                            shutil.rmtree(old)
            except OSError as exc:
                warnings.append('RSS 已发布，但旧文件清理或落盘确认未完成；请重新发布以重试：'+str(exc))
            return dict(revision=hashlib.sha256(state).hexdigest(), episodes=online,
                        removed=removed, warnings=warnings)


def configure(path, config):
    """Do not overwrite a live directory's identity when deploying a new profile."""
    pub = Publisher(config['root'],config['base_url'],config['token'])
    path = Path(path)
    with (pub.root/'publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        Publisher(config['root'],config['base_url'],config['token'])
        temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with open(temp,'x',opener=lambda name,flags:os.open(name,flags,0o600)) as stream:
                json.dump(config,stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp,path)
        finally:
            temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('action', choices=['status', 'prepare', 'commit', 'abort', 'remove'])
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    pub = Publisher(config['root'], config['base_url'], config['token'])
    request = json.load(sys.stdin) if args.action != 'status' else {}
    if args.action == 'status':
        result = pub.status()
    elif args.action == 'prepare':
        pub.prepare(request['batch'])
        result = {'ready': True}
    elif args.action == 'abort':
        pub._check_batch(request['batch'])
        shutil.rmtree(pub.root/'.staging'/request['batch'], ignore_errors=True)
        result = {'aborted': True}
    elif args.action == 'remove':
        result = pub.remove(request['ids'], request['revision'])
    else:
        result = pub.commit(request['episodes'], request['batch'], request['revision'])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
