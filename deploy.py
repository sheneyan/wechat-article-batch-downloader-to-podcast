#!/usr/bin/env python3
"""Deploy to the saved SSH profile; optionally generate a static nginx snippet."""
import argparse
import json
from pathlib import Path
from wechat2podcast.client import Client


def main():
    parser=argparse.ArgumentParser(description='部署发布组件；不自动修改域名、证书或 nginx')
    parser.add_argument('--config',default='.private/publish.json')
    parser.add_argument('--nginx-snippet',help='将 nginx location 模板写入指定本地文件，供站点管理员安装')
    args=parser.parse_args()
    client=Client(args.config)
    print(client.test_connection()['message'])
    print(client.deploy()['message'])
    if args.nginx_snippet:
        root=client.config['remote_root']+'/www'
        if '$' in root or '\\' in root:
            raise ValueError('nginx 模板不支持含 $ 或反斜线的存储目录')
        snippet='''# Include in the intended existing HTTPS server block.
location ^~ /wechat/ {
    charset utf-8;
    charset_types application/rss+xml;
    root ROOT_PLACEHOLDER;
    autoindex off;
    open_file_cache off;
    try_files $uri =404;
    types { application/rss+xml xml; audio/mpeg mp3; }
    default_type application/octet-stream;
    limit_except GET HEAD { deny all; }
    add_header X-Wechat-Origin "wechat2podcast" always;
    add_header Cache-Control "no-cache" always;
    access_log off;
}
'''.replace('ROOT_PLACEHOLDER',json.dumps(root,ensure_ascii=False))
        output=Path(args.nginx_snippet)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(snippet)
        print('nginx 模板已保存：'+str(output))


if __name__ == '__main__':
    main()
