"""Read-only local environment checks before starting expensive speech work."""
import shutil
import subprocess
import sys


def check_dependencies(voice='Tingting'):
    tools={name:shutil.which(name) or '' for name in ('say','ffmpeg','ffprobe','ssh','scp','tailscale')}
    missing=[name for name,path in tools.items() if not path and name!='tailscale']
    if sys.version_info < (3,11):
        missing.insert(0,'Python 3.11+')
    if tools['say']:
        result=subprocess.run([tools['say'],'-v','?'],check=True,capture_output=True,text=True,timeout=15)
        if not voice or not any(line.startswith(voice+' ') for line in result.stdout.splitlines()):
            missing.append('系统语音:'+voice)
    version='.'.join(map(str,sys.version_info[:3]))
    return dict(available=not missing,missing=missing,python_version=version,tools=tools,
                message=('本机环境可用：Python '+version+'、系统语音 '+voice+'、ffmpeg/ffprobe、SSH。') if not missing
                else '缺少或需要更新：'+'、'.join(missing)+'。请安装或在设置中选择正确的 Python/系统语音。')


def require_audio(voice='Tingting'):
    result=check_dependencies(voice)
    missing=[name for name in result['missing'] if name not in ('ssh','scp')]
    if missing:
        raise ValueError('无法开始转换，缺少：'+'、'.join(missing))
