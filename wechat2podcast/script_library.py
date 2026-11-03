"""Adapt verified spoken scripts to the complete local audio library."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from .core import CHINA
from .inbox_client import verify_document
from .library import atomic_json


def import_scripts(library,raw):
    raw=Path(raw)
    if (raw/'documents').is_dir():
        raw=raw/'documents'
    entries=[]
    for path in sorted(raw.glob('*.json')):
        if path.name=='state.json':
            continue
        original=json.loads(path.read_text())
        doc=verify_document(original)
        aid=hashlib.sha256(('grok-script:'+doc['id']).encode()).hexdigest()[:20]
        folder=library.root/aid
        saved=folder/'article.json'
        previous=json.loads(saved.read_text()) if saved.exists() else {}
        if previous.get('inbox_sha256') and previous['inbox_sha256']!=original['sha256']:
            raise ValueError('口播稿编号冲突：'+doc['id']+'。本地内容已保留，请让发送方使用 -v2 等新的修订编号。')
        is_test=(doc['id'].startswith(('grok-connectivity-','codex-api-test-')) or
                 any(term in doc['title'] for term in ('接口连通性测试','收稿接口复测','接口写入测试')))
        published=doc['date']+'T00:00:00+08:00'
        try:
            received=datetime.fromisoformat(original['created_at']).astimezone(CHINA)
            if received.date().isoformat()==doc['date']:
                published=received.isoformat()
        except (KeyError,ValueError):
            pass
        article=dict(id=aid,title=doc['title'],account='每日 X',author='Grok',
                     source_kind='grok',source_id=doc['id'],is_test=is_test,
                     source_url=doc['source_urls'][0] if doc['source_urls'] else '',
                     source_urls=doc['source_urls'],source_path=str(path.with_suffix('.txt').resolve()),
                     published_at=published,imported_at=previous.get('imported_at') or datetime.now(CHINA).isoformat(timespec='seconds'),
                     speech=doc['text'],notes=doc['notes'],inbox_sha256=original['sha256'],
                     content_sha256=hashlib.sha256(doc['text'].encode()).hexdigest())
        entries.append((saved,article,previous!=article))
    # Validate the complete download set before changing any library metadata.
    for saved,article,changed in entries:
        if changed:
            atomic_json(saved,article)
    return dict(imported=sum(changed for _,_,changed in entries),test_count=sum(a['is_test'] for _,a,_ in entries))
