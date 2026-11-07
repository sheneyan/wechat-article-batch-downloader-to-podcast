import argparse
import json
import subprocess
import sys
from pathlib import Path

from .client import Client
from .library import Library


def main():
    parser = argparse.ArgumentParser(description='微信文章 → Mac TTS → 统一播客，最多在线 20 集')
    parser.add_argument('--library', default='.local/library')
    parser.add_argument('--config', default='.private/publish.json')
    commands = parser.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('scan', help='扫描归档，仅保存到本地库')
    scan.add_argument('archive', nargs='?', default=str(Path.home()/'Documents/wechat_archived'))
    commands.add_parser('list', help='列出本地文章')
    for action in ['render', 'preview']:
        render = commands.add_parser(action, help='转换完整文章' if action == 'render' else '生成本地试听')
        render.add_argument('ids', nargs='*')
        render.add_argument('--all', action='store_true')
        render.add_argument('--voice', default='Tingting')
        render.add_argument('--rate', type=int, default=180)
        if action == 'preview':
            render.add_argument('--characters', type=int, default=260)
    publish = commands.add_parser('publish', help='默认仅预览，--apply 才上传并更新 RSS')
    publish.add_argument('ids', nargs='+')
    publish.add_argument('--apply', action='store_true')
    commands.add_parser('status', help='查看服务端在线目录')
    commands.add_parser('url', help='显示私人订阅地址')
    args = parser.parse_args()
    library = Library(args.library)
    if args.command in ['scan', 'list']:
        articles = library.scan(args.archive) if args.command == 'scan' else library.articles()
        for a in articles:
            ready = (library.root/a['id']/'audio.mp3').exists()
            print(f"{a['id']}  {a['published_at'][:10]}  {'已转换' if ready else '待转换'}  {a['account']}｜{a['title']}")
        print(f'共 {len(articles)} 篇；未上传。')
    elif args.command in ['render', 'preview']:
        if args.all and args.ids:
            raise ValueError('--all 和文章 ID 请二选一')
        articles = library.articles() if args.all else [library.find(i) for i in args.ids]
        if not articles:
            raise ValueError('请指定文章 ID 或 --all')
        if args.rate <= 0:
            raise ValueError('语速必须大于零')
        for article in articles:
            print('转换：'+article['title'], flush=True)
            path, info, cached = library.render(article, args.voice, args.rate,
                                                args.command == 'preview', getattr(args, 'characters', 260))
            print(f"{'复用' if cached else '生成'} {path.resolve()}  {info['duration']:.1f} 秒 / {info['audio_bytes']/1024/1024:.2f} MiB", flush=True)
        print('仅保存到 Mac，未上传。')
    elif args.command == 'url':
        print(json.loads(Path(args.config).read_text())['base_url']+'/feed.xml')
    else:
        client = Client(args.config)
        if args.command == 'status':
            current = client.remote('status')
            for a in current['episodes']:
                print(f"{a['id']}  {a['published_at'][:10]}  {a['account']}｜{a['title']}")
            print(f"在线 {len(current['episodes'])}/20 集，音频 {sum(a['audio_bytes'] for a in current['episodes'])/1024/1024:.2f} MiB")
            return
        articles = [library.find(i) for i in args.ids]
        if len({a['id'] for a in articles}) != len(articles):
            raise ValueError('重复选择了同一篇文章')
        incoming, files = zip(*(library.publishable(a) for a in articles))
        current, online, removed = client.plan(incoming)
        for a in incoming:
            print('上线：'+a['account']+'｜'+a['title'])
        for a in removed:
            print('淘汰（Mac 保留）：'+a['account']+'｜'+a['title'])
        print(f"发布后在线 {len(online)}/20 集，音频 {sum(a['audio_bytes'] for a in online)/1024/1024:.2f} MiB")
        if args.apply:
            result = client.publish(incoming, files, current['revision'])
            print(f"发布完成，在线 {len(result['episodes'])}/20 集。")
            for warning in result.get('warnings', []):
                print(warning, file=sys.stderr)
        else:
            print('仅预览；添加 --apply 才会上传。')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
