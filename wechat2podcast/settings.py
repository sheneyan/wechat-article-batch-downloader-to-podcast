"""User-editable publication settings; credentials stay in the user's SSH agent/config."""
import json
import re
import secrets
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit

from .library import atomic_json


def load_config(path):
    path = Path(path)
    cfg = json.loads(path.read_text()) if path.exists() else {}
    host = cfg.get('ssh_host', '')
    user = cfg.get('ssh_user', '')
    if '@' in host:
        user, host = host.rsplit('@', 1)
    root = cfg.get('remote_root', '/srv/wechat2podcast')
    return {**cfg, 'ssh_host':host, 'ssh_user':user, 'ssh_port':cfg.get('ssh_port', 22),
            'identity_file':cfg.get('identity_file',''), 'remote_root':root,
            'remote_code':root+'/app', 'remote_config':root+'/config.json',
            'base_url':cfg.get('base_url',''), 'token':cfg.get('token',''),
            'feed_title':cfg.get('feed_title','微信文章'),'auto_publish':False}


def save_config(path, settings):
    host = str(settings.get('ssh_host','')).strip()
    user = str(settings.get('ssh_user','')).strip()
    if '@' in host and not user:
        user, host = host.rsplit('@',1)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',host):
        raise ValueError('SSH 主机请填写主机名、Tailscale 名称或 IPv4 地址')
    if user and not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',user):
        raise ValueError('SSH 用户名无效')
    port = int(settings.get('ssh_port',22))
    if not 1 <= port <= 65535:
        raise ValueError('SSH 端口应在 1–65535 之间')
    root = str(settings.get('remote_root','')).strip().rstrip('/')
    if not root.startswith('/') or root == '' or '..' in PurePosixPath(root).parts or any(ord(c)<32 for c in root):
        raise ValueError('服务器目录请填写不含 .. 的绝对路径')
    if root in ('/', '/etc', '/usr', '/var', '/home', '/srv', '/root'):
        raise ValueError('请选择专用于此节目的服务器子目录')
    url = urlsplit(str(settings.get('base_url','')).strip())
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('节目地址必须是无账号密码、查询参数的 HTTPS 地址')
    # Force malformed port errors before saving a profile.
    url.port
    old = load_config(path)
    token = old.get('token') or secrets.token_hex(20)
    suffix = url.path.rstrip('/')
    if suffix.endswith('/feed.xml'):
        suffix = suffix[:-9]
    if suffix in ('', '/wechat'):
        suffix = '/wechat/'+token
    match = re.fullmatch(r'/wechat/([A-Za-z0-9_-]+)',suffix)
    if not match:
        raise ValueError('节目路径请使用 /wechat/节目标识，或仅填写服务器 HTTPS 域名')
    token = match[1]
    identity = str(settings.get('identity_file','')).strip()
    title=str(settings.get('feed_title',old.get('feed_title','微信文章'))).strip()
    if not title or len(title)>100:
        raise ValueError('节目名称应为 1–100 个字符')
    if identity:
        identity = str(Path(identity).expanduser().resolve())
    config = dict(ssh_host=host, ssh_user=user, ssh_port=port, identity_file=identity,
                  remote_root=root, remote_code=root+'/app', remote_config=root+'/config.json',
                  base_url=urlunsplit((url.scheme,url.netloc,suffix,'','')), token=token,feed_title=title,auto_publish=False)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_json(path,config)
    path.chmod(0o600)
    return config
