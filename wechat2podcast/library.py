"""The complete Mac library is independent of the bounded online catalogue."""
import json
import os
import tempfile
import re
import shutil
from pathlib import Path
from datetime import datetime

from .audio import audio_info, preview_text, render_audio
from .core import scan_archive, CHINA


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Library:
    def __init__(self, root):
        self.root = Path(root)

    def deleted_ids(self):
        path = self.root/'.deleted.json'
        return set(json.loads(path.read_text())) if path.exists() else set()

    def delete_articles(self, ids):
        if not ids or len(set(ids)) != len(ids) or any(not isinstance(aid,str) or not re.fullmatch(r'[0-9a-f]{20}',aid) for aid in ids):
            raise ValueError('请选择有效且不重复的完整文章编号')
        deleted = self.deleted_ids()
        known = {a['id'] for a in self.articles()} | deleted
        if any(aid not in known for aid in ids):
            raise ValueError('文章已变化，请刷新列表后重试')
        paths = []
        for parent in (self.root,self.root.parent/'previews'):
            if parent.is_symlink():
                raise ValueError('不能删除符号链接目录内的文件')
            for aid in ids:
                path = parent/aid
                if path.is_symlink() or path.resolve().parent != parent.resolve():
                    raise ValueError('不能删除符号链接或本地库以外的文件')
                paths.append(path)
        # Persist intent before cleanup so interruption cannot reimport deleted entries.
        atomic_json(self.root/'.deleted.json',sorted(deleted | set(ids)))
        for path in paths:
            if path.exists():
                shutil.rmtree(path)

    def scan(self, archive):
        deleted = self.deleted_ids()
        found = [a for a in scan_archive(archive) if a['id'] not in deleted]
        for article in found:
            folder = self.root/article['id']
            folder.mkdir(parents=True, exist_ok=True)
            saved=folder/'article.json'
            previous=json.loads(saved.read_text()) if saved.exists() else {}
            article['imported_at']=previous.get('imported_at') or datetime.now(CHINA).isoformat(timespec='seconds')
            # Store the exact text with the metadata; existing MP3 remains until a new render succeeds.
            atomic_json(folder/'article.json', article)
        return found

    def articles(self):
        deleted = self.deleted_ids()
        result = [json.loads(p.read_text()) for p in self.root.glob('*/article.json') if p.parent.name not in deleted]
        return sorted(result, key=lambda a: (a['published_at'], a['id']), reverse=True)

    def find(self, prefix):
        matches = [a for a in self.articles() if a['id'].startswith(prefix)]
        if len(matches) != 1:
            raise ValueError(f'文章 ID 不存在或不唯一: {prefix}')
        return matches[0]

    def render(self, article, voice='Tingting', rate=180, preview=False, characters=260):
        if article.get('is_test'):
            raise ValueError('测试稿不参与语音转换或发布')
        folder = self.root/article['id']
        if preview:
            folder = self.root.parent/'previews'/article['id']
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/'audio.mp3'
        info_path = folder/'audio.json'
        if not preview and path.exists() and info_path.exists():
            old = json.loads(info_path.read_text())
            if (old.get('content_sha256'), old.get('voice'), old.get('rate')) == (article['content_sha256'], voice, rate):
                actual = audio_info(path)
                if actual['audio_sha256'] == old['audio_sha256']:
                    return path, old, True
        speech = preview_text(article['speech'], characters) if preview else article['speech']
        (folder/'speech.txt').write_text(speech, encoding='utf-8')
        metadata = render_audio(folder/'speech.txt', path, voice, rate)
        metadata.update(content_sha256=article['content_sha256'], preview=preview)
        atomic_json(info_path, metadata)
        return path, metadata, False

    def publishable(self, article):
        if article.get('is_test'):
            raise ValueError('测试稿不参与语音转换或发布')
        folder = self.root/article['id']
        metadata = json.loads((folder/'audio.json').read_text())
        if metadata.get('preview') or metadata['content_sha256'] != article['content_sha256']:
            raise ValueError('请先转换最新的完整文章: '+article['id'])
        actual = audio_info(folder/'audio.mp3')
        if actual['audio_sha256'] != metadata['audio_sha256']:
            raise ValueError('本地音频校验失败: '+article['id'])
        public = {k:article[k] for k in ['id', 'title', 'account', 'author', 'source_url', 'published_at']}
        public['source_kind']=article.get('source_kind','wechat')
        public['date_source']='published'
        if not public['published_at']:
            if not article.get('imported_at'):
                raise ValueError('请重新扫描归档，以记录缺失日期文章的首次导入时间')
            public['published_at']=article['imported_at']
            public['date_source']='imported'
        public.update(actual)
        return public, folder/'audio.mp3'
