#!/usr/bin/env python3
"""Install a separate script inbox behind an existing HTTPS nginx site."""
import argparse
import json
import re
import secrets
import shlex
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from wechat2podcast.client import Client
from wechat2podcast.library import atomic_json


def private_json(path,data):
    atomic_json(path,data)
    path.chmod(0o600)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',default='.private/publish.json')
    parser.add_argument('--nginx-site',required=True,help='Existing HTTPS site containing the wechat2podcast include')
    args=parser.parse_args()
    client=Client(args.profile)
    root=client.config['remote_root']
    folder=root+'/inbox'
    code=client.config['remote_code']
    profile=Path('.private/inbox-server.json')
    profile.parent.mkdir(mode=0o700,exist_ok=True)
    existing=client.ssh('if test -f '+shlex.quote(folder+'/config.json')+'; then cat '+shlex.quote(folder+'/config.json')+'; else printf "{}"; fi')
    remote=json.loads(existing.stdout)
    if profile.exists():
        config=json.loads(profile.read_text())
        if remote and config!=remote:
            raise RuntimeError('Local/remote inbox profiles differ; refusing implicit token rotation')
    elif remote:
        config=remote
    else:
        config=dict(database=folder+'/scripts.sqlite3',port=18769,
                    write_token=secrets.token_hex(32),read_token=secrets.token_hex(32))
    private_json(profile,config)
    user=client.ssh('id -un').stdout.strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',user):
        raise ValueError('Unexpected SSH username')
    client.ssh('mkdir -p '+shlex.quote(folder)+' '+shlex.quote(code+'/wechat2podcast')+' && chmod 700 '+shlex.quote(folder))
    def upload(source,destination):
        subprocess.run(['scp','-q',*client.ssh_options(scp=True),str(source),client.host+':'+destination],check=True,timeout=180)
    upload(profile,folder+'/config.json')
    upload(Path(__file__).resolve().parents[1]/'wechat2podcast/inbox.py',code+'/wechat2podcast/inbox.py')
    client.ssh('chmod 600 '+shlex.quote(folder+'/config.json'))
    unit=f'''[Unit]
Description=Private spoken-script inbox
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={code.replace('%','%%')}
ExecStart=/usr/bin/python3 -B -m wechat2podcast.inbox --config {json.dumps(folder+'/config.json')}
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={json.dumps(folder)}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
'''
    unit_file=Path('.private/wechat2podcast-inbox.service')
    unit_file.write_text(unit)
    upload(unit_file,folder+'/unit.service')
    snippet=f'''# Dedicated text intake; does not touch /wechat/ or the existing relay.
location ^~ /brief-inbox/ {{
    client_max_body_size 256k;
    proxy_pass http://127.0.0.1:{int(config['port'])}/;
    proxy_set_header Host $host;
    proxy_set_header Authorization $http_authorization;
    proxy_read_timeout 20s;
    proxy_connect_timeout 5s;
    access_log off;
}}
'''
    snippet_file=Path('.private/wechat2podcast-inbox.conf')
    snippet_file.write_text(snippet)
    upload(snippet_file,folder+'/nginx.conf')
    client.ssh('sudo -n install -m 644 '+shlex.quote(folder+'/unit.service')+
               ' /etc/systemd/system/wechat2podcast-inbox.service && sudo -n systemctl daemon-reload && '+
               'sudo -n systemctl enable wechat2podcast-inbox.service && sudo -n systemctl restart wechat2podcast-inbox.service')
    configure='''from pathlib import Path
import subprocess,datetime,shutil
site=Path(SITE)
text=site.read_text()
marker='    include /etc/nginx/snippets/wechat2podcast.conf;'
addition='    include /etc/nginx/snippets/wechat2podcast-inbox.conf;'
if addition not in text and text.count(marker)!=1:
 raise RuntimeError('Existing HTTPS site not recognized; no nginx change made')
backup=Path(ROOT)/'nginx-backups'
backup.mkdir(exist_ok=True)
shutil.copy2(site,backup/('before-inbox-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.conf'))
snippet=Path('/etc/nginx/snippets/wechat2podcast-inbox.conf')
previous=snippet.read_bytes() if snippet.exists() else None
shutil.copyfile(SNIPPET,snippet)
try:
 if addition not in text: site.write_text(text.replace(marker,addition+'\\n'+marker))
 subprocess.run(['nginx','-t'],check=True)
 subprocess.run(['systemctl','reload','nginx'],check=True)
except BaseException:
 site.write_text(text)
 if previous is None: snippet.unlink(missing_ok=True)
 else: snippet.write_bytes(previous)
 subprocess.run(['nginx','-t'],check=True)
 subprocess.run(['systemctl','reload','nginx'],check=True)
 raise
print('Text inbox nginx route configured')
'''.replace('SITE',repr(args.nginx_site)).replace('ROOT',repr(root)).replace('SNIPPET',repr(folder+'/nginx.conf'))
    result=client.ssh('sudo -n python3 -c '+shlex.quote(configure))
    print(result.stdout.strip())
    print(result.stderr.strip())
    url=urlsplit(client.config['base_url'])
    base=url.scheme+'://'+url.netloc+'/brief-inbox'
    private_json(Path('.private/inbox-reader.json'),dict(base_url=base,read_token=config['read_token']))
    private_json(Path('.private/inbox-writer.json'),dict(base_url=base,write_token=config['write_token']))
    print('Inbox deployed. Private writer/reader profiles saved under .private/.')


if __name__=='__main__':
    main()
