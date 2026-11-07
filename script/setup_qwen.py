#!/usr/bin/env python3
"""Install a pinned, isolated local TTS runtime and configure the Mac app."""
import argparse
import concurrent.futures
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from wechat2podcast import qwen
from wechat2podcast.remote import sha256_file


def download_model(target):
    base='https://modelscope.cn/models/'+qwen.MODEL_ID
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    api='https://modelscope.cn/api/v1/models/'+qwen.MODEL_ID+'/repo/files?Revision='+qwen.MODEL_REVISION+'&Recursive=true'
    with opener.open(api,timeout=30) as response:meta=json.load(response)
    if meta.get('Code')!=200:raise ValueError('无法读取 ModelScope 模型清单')
    files=[entry for entry in meta['Data']['Files'] if entry['Type']=='blob']
    target.mkdir(parents=True,exist_ok=True)
    for entry in files:
        relative=Path(entry['Path'])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('模型清单包含无效路径')
        dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        size=entry['Size'];digest=entry['Sha256']
        if dest.is_file() and dest.stat().st_size==size and sha256_file(dest)==digest:continue
        url=base+'/resolve/'+qwen.MODEL_REVISION+'/'+urllib.parse.quote(entry['Path'],safe='/')
        step=16*1024*1024
        def part(start):
            end=min(start+step,size)-1
            path=dest.with_name(dest.name+f'.{start}.part')
            if not path.exists() or path.stat().st_size!=end-start+1:
                subprocess.run(['curl','--noproxy','*','--fail','--location','--silent','--show-error','--retry','2','--max-time','180','--range',f'{start}-{end}',url,'--output',str(path)],check=True)
            if path.stat().st_size!=end-start+1:raise ValueError('模型下载长度不符：'+str(relative))
            return path
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            parts=list(pool.map(part,range(0,size,step)))
        temp=dest.with_name(dest.name+'.download');actual=hashlib.sha256()
        with temp.open('wb') as output:
            for path in parts:
                with path.open('rb') as source:
                    while block:=source.read(1024*1024):actual.update(block);output.write(block)
        if actual.hexdigest()!=digest:
            temp.unlink(missing_ok=True)
            for path in parts:path.unlink(missing_ok=True)
            raise ValueError('模型 SHA256 校验失败，损坏分块已清理，请重跑：'+str(relative))
        temp.replace(dest)
        for path in parts:path.unlink()
        print('已校验 '+str(relative),flush=True)
    (target/'download-manifest.json').write_text(json.dumps(dict(model=qwen.MODEL_ID,revision=qwen.MODEL_REVISION,files=files),ensure_ascii=False,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-model',type=Path,help='复用已下载 CustomVoice 模型目录，不复制或上传权重')
    parser.add_argument('--speed',type=float,default=1.25)
    parser.add_argument('--replace-config',action='store_true',help='显式替换已有 Qwen 配置')
    args=parser.parse_args()
    if platform.system()!='Darwin' or platform.machine()!='arm64':raise ValueError('此运行方案需要 Apple Silicon Mac')
    cfg=qwen.defaults();profile=Path.home()/'Library/Application Support/Wechat2Podcast/Podcast/tts.json'
    if profile.exists() and not args.replace_config:
        print('已有 Qwen 配置，未覆盖；检查已有配置。');print(qwen.check(qwen.load(profile))['message']);return
    if not .75<=args.speed<=2:raise ValueError('倍速须在 0.75–2.0 之间')
    uv=shutil.which('uv')
    if not uv:raise ValueError('请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/')
    python=Path(cfg['python']);venv=python.parent.parent
    if not python.exists():subprocess.run([uv,'venv','--python','3.11',str(venv)],check=True)
    subprocess.run([uv,'pip','install','--python',str(python),'-r',str(ROOT/'script/requirements-qwen.txt')],check=True)
    if args.source_model:cfg['model']=str(args.source_model.expanduser().resolve())
    else:download_model(Path(cfg['model']))
    cfg['speed']=args.speed
    print(qwen.check(cfg)['message'])
    qwen.save(profile,cfg)
    print('Qwen 已配置。重新打开 App，在音色列表中选择 Qwen 男声即可试听和生成。')
    print('配置：'+str(profile))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
