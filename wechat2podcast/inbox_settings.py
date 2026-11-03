"""Independent, private read-only inbox connection profile for the Mac app."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from .library import atomic_json


def load(path):
    path=Path(path)
    return json.loads(path.read_text()) if path.exists() else dict(base_url='',read_token='')


def save(path,settings):
    url=str(settings.get('base_url','')).strip().rstrip('/')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in url):
        raise ValueError('收件地址必须是无账号密码、查询参数的 HTTPS 根地址')
    parsed.port
    token=str(settings.get('read_token','')).strip()
    if not 16<=len(token)<=1024 or any(c.isspace() for c in token):
        raise ValueError('请填写有效的口播稿读取密钥')
    previous=load(path)
    if previous['base_url'] and urlsplit(previous['base_url']).netloc!=parsed.netloc and token==previous['read_token']:
        raise ValueError('修改收件主机后，请填写对应主机的读取密钥')
    result=dict(base_url=url,read_token=token)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    atomic_json(path,result)
    path.chmod(0o600)
    return result


def required(path):
    cfg=load(path)
    if not cfg.get('base_url') or not cfg.get('read_token'):
        raise ValueError('请先在设置中配置口播稿收件地址与读取密钥')
    return cfg
