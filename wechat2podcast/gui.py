"""One JSON request/response per invocation for the native Mac interface."""
import json
import subprocess
import sys
import os
import signal
from pathlib import Path

from .client import Client
from .library import Library
from .settings import load_config, save_config
from .dependencies import check_dependencies, system_voices
from . import inbox_settings
from .inbox_client import fetch, request as inbox_request
from .script_library import import_scripts


def dashboard(root):
    library = Library(root)
    articles = []
    for article in library.articles():
        folder = library.root/article['id']
        path = folder/'audio.mp3'
        info_path = folder/'audio.json'
        info = json.loads(info_path.read_text()) if info_path.exists() else {}
        state = 'missing'
        if path.exists():
            ready = (info.get('content_sha256') == article['content_sha256'] and
                     info.get('audio_bytes') == path.stat().st_size and not info.get('preview', True))
            state = 'ready' if ready else 'stale'
        public = {k:article[k] for k in ('id','title','account','author','published_at','source_url','source_path')}
        public.update(source_kind=article.get('source_kind','wechat'),source_id=article.get('source_id',''),is_test=article.get('is_test',False))
        public.update(local_state=state, audio_path=str(path.resolve()) if path.exists() else None,
                      **{k:info.get(k) for k in ('duration','audio_bytes','audio_sha256')})
        articles.append(public)
    return dict(articles=articles,library=str(library.root.resolve()))


def handle(req):
    action = req['action']
    root = Path(req['library']).expanduser()
    config = Path(req['config']).expanduser()
    library = Library(root)
    inbox_profile=root.parent/'inbox-reader.json'
    if action=='inbox_config':
        return inbox_settings.load(inbox_profile)
    if action=='save_inbox_config':
        return inbox_settings.save(inbox_profile,req['settings'])
    if action=='test_inbox':
        inbox_request(inbox_settings.required(inbox_profile),'/v1/scripts?after=0&limit=1')
        return dict(message='口播稿收件服务连接成功，可读取稿件目录。')
    if action=='pull_scripts':
        downloaded=fetch(inbox_settings.required(inbox_profile),root.parent/'inbox/raw')
        imported=import_scripts(library,downloaded['output'])
        return {**dashboard(root),**imported,'downloaded':downloaded['downloaded']}
    if action=='article_detail':
        article=library.find(req['id'])
        return dict(id=article['id'],title=article['title'],text=article['speech'],notes=article.get('notes',''),
                    source_kind=article.get('source_kind','wechat'),is_test=article.get('is_test',False))
    if action == 'dependencies':
        return check_dependencies(req.get('voice','Tingting'))
    if action == 'voices':
        return dict(voices=system_voices())
    if action == 'dashboard':
        return dashboard(root)
    if action == 'delete_articles':
        library.delete_articles(req['ids'])
        return dashboard(root)
    if action == 'scan':
        library.scan(Path(req['archive']).expanduser())
        return dashboard(root)
    if action in ('render','preview'):
        rate = int(req.get('rate',180))
        if not 1 <= rate <= 500:
            raise ValueError('语速请选择 1–500')
        path,info,cached = library.render(library.find(req['id']),req.get('voice','Tingting'),rate,
                                         action=='preview',int(req.get('characters',260)))
        return dict(audio_path=str(path.resolve()),cached=cached,**info)
    if action == 'config':
        return load_config(config)
    if action == 'save_config':
        return save_config(config,req['settings'])
    if action == 'url':
        cfg = load_config(config)
        if not cfg['base_url']:
            raise ValueError('尚未配置节目地址')
        return {'rss_url':cfg['base_url']+'/feed.xml'}
    client = Client(config)
    if action == 'test_connection':
        return client.test_connection()
    if action == 'deploy':
        return client.deploy()
    if action == 'online':
        return {**client.remote('status'),'rss_url':client.config['base_url']+'/feed.xml',
                'base_url':client.config['base_url']}
    if action == 'unpublish':
        return client.remote('remove',dict(ids=req['ids'],revision=req['revision']))
    if action not in ('plan','publish'):
        raise ValueError('未知操作: '+action)
    articles = [library.find(aid) for aid in req['ids']]
    if len({a['id'] for a in articles}) != len(articles) or not articles:
        raise ValueError('请选择不重复的文章')
    incoming, files = zip(*(library.publishable(a) for a in articles))
    if action == 'plan':
        current,online,removed = client.plan(incoming)
        return dict(revision=current['revision'],incoming=list(incoming),removed=removed,
                    online=online,total_bytes=sum(ep['audio_bytes'] for ep in online))
    # Check the exact preview revision before transferring, and again atomically on the server.
    current = client.remote('status')
    if current['revision'] != req['revision']:
        raise ValueError('在线目录已变化，请关闭预览并重新选择发布')
    return client.publish(incoming,files,req['revision'])


def main():
    # Give the bridge and its speech/ffmpeg/SSH children an isolated process group.
    # Native cancellation can then stop the group while Python unwinds temporary-file cleanup.
    # Foundation Process already makes its child a process-group leader. Such a
    # process cannot call setsid(), but its existing group is safe to cancel.
    if os.getpgrp() != os.getpid():
        os.setsid()
    def cancel(_signum, _frame):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        os.killpg(os.getpgrp(), signal.SIGTERM)
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, cancel)
    request = json.load(sys.stdin)
    if sys.version_info < (3,11) and request.get('action') != 'dependencies':
        raise ValueError('请选择 Python 3.11 或更新版本；当前为 '+sys.version.split()[0])
    result = handle(request)
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('任务已停止。若停止的是发布任务，请刷新线上目录确认最终结果。',file=sys.stderr)
        sys.exit(130)
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        message = str(exc)
        if isinstance(exc,subprocess.CalledProcessError) and exc.stderr:
            message += '\n'+str(exc.stderr)
        print(message,file=sys.stderr)
        sys.exit(1)
