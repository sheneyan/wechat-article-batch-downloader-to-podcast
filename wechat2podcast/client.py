"""Tailnet SSH upload with optimistic concurrency and explicit application."""
import json
import shlex
import subprocess
import uuid
import sys
from pathlib import Path

from .core import select_online
from .settings import load_config


class Client:
    def __init__(self, config_path):
        self.config = load_config(config_path)
        host = self.config['ssh_host']
        if not host:
            raise ValueError('请先填写并保存播客服务器配置')
        self.host = (self.config['ssh_user']+'@' if self.config['ssh_user'] else '')+host

    def ssh_options(self, scp=False):
        options = ['-o','BatchMode=yes','-o','ConnectTimeout=10']
        port = self.config.get('ssh_port',22)
        # An omitted default port preserves ~/.ssh/config aliases and their Port settings.
        if port != 22:
            options += ['-P' if scp else '-p',str(port)]
        if self.config.get('identity_file'):
            options += ['-i',self.config['identity_file'],'-o','IdentitiesOnly=yes']
        return options

    def ssh(self, command, request=None, timeout=180):
        return subprocess.run(['ssh',*self.ssh_options(),self.host,command],
                              input=json.dumps(request or {}),capture_output=True,text=True,
                              timeout=timeout,check=True)

    def remote(self, action, request=None):
        args = ['python3', '-m', 'wechat2podcast.remote', '--config', self.config['remote_config'], action]
        command = 'cd '+shlex.quote(self.config['remote_code'])+' && '+shlex.join(args)
        result = self.ssh(command, request)
        return json.loads(result.stdout)

    def plan(self, incoming):
        current = self.remote('status')
        online, removed = select_online(current['episodes'], incoming)
        return current, online, removed

    def publish(self, incoming, files, revision):
        batch = uuid.uuid4().hex
        self.remote('prepare', {'batch': batch})
        try:
            for ep, source in zip(incoming, files, strict=True):
                destination = self.config['remote_root']+'/.staging/'+batch+'/'+ep['audio_file']
                subprocess.run(['scp', '-q', *self.ssh_options(scp=True),
                                str(source), self.host+':'+destination], check=True, timeout=1800)
            return self.remote('commit', {'batch': batch, 'revision': revision, 'episodes': incoming})
        finally:
            if sys.exc_info()[0] is not KeyboardInterrupt:
                try:
                    self.remote('abort', {'batch': batch})
                except (OSError, subprocess.SubprocessError):
                    print('上传暂存目录清理未完成，下次发布会清理过期暂存文件。', file=sys.stderr)

    def test_connection(self):
        result = self.ssh("python3 -c 'import sys; assert sys.version_info >= (3,10); print(\"SSH 连接成功，服务器 Python 版本可用\")'")
        return {'message':result.stdout.strip()}

    def deploy(self):
        root = self.config['remote_root']
        code = self.config['remote_code']
        self.ssh('mkdir -p '+shlex.quote(root)+' '+shlex.quote(code+'/wechat2podcast'))
        sources = [str(p) for p in Path(__file__).parent.glob('*.py')]
        subprocess.run(['scp','-q',*self.ssh_options(scp=True),*sources,self.host+':'+code+'/wechat2podcast/'],
                       check=True,timeout=180)
        remote = {k:self.config[k] for k in ('base_url','token')}
        remote['root'] = root
        write = ('import json,sys; from wechat2podcast.remote import configure; '
                 'configure('+repr(self.config['remote_config'])+',json.load(sys.stdin))')
        self.ssh('cd '+shlex.quote(code)+' && python3 -c '+shlex.quote(write),remote)
        self.remote('status')
        return {'message':'发布组件已部署/更新。HTTPS 站点需将 /wechat/ 映射到 '+root+'/www；域名、证书和 nginx 不由此按钮修改。'}
