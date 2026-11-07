"""Local Qwen configuration and process boundary; MLX stays out of the GUI bridge."""
import hashlib
import json
import math
import os
import re
import subprocess
import time
import shutil
from pathlib import Path

from .library import atomic_json

MODEL_ID='mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit'
MODEL_REVISION='3624a3894b6b8e09d202873a2e240b1326e43128'
SPEAKERS={'Uncle_Fu':'低沉男声','Dylan':'北京口音男声','Eric':'四川口音男声'}
INSTRUCTION='用平实自然的语气清楚朗读，节奏紧凑，不要抒情，不要夸张，不要拖长句尾。'


def defaults():
    root=Path.home()/'Library/Application Support/Wechat2Podcast/QwenTTS'
    return dict(python=str(root/'venv/bin/python'),model=str(root/'models/1.7B-CustomVoice-4bit'),speed=1.25)


def load(path):
    path=Path(path)
    return {**defaults(),**json.loads(path.read_text())} if path.exists() else defaults()


def validate(cfg):
    values={k:cfg.get(k,v) for k,v in defaults().items()}
    try:
        speed=float(values['speed'])
    except (TypeError,ValueError):
        raise ValueError('Qwen 倍速请选择 0.75–2.0')
    if not math.isfinite(speed) or not .75<=speed<=2:
        raise ValueError('Qwen 倍速请选择 0.75–2.0')
    values['speed']=speed
    for key in ('python','model'):
        path=Path(values[key]).expanduser()
        if not path.is_absolute():
            raise ValueError('Qwen 路径请填写绝对路径')
        values[key]=str(path.resolve()) if key=='model' else str(path.absolute())
    if not os.access(values['python'],os.X_OK) or not Path(values['python']).is_file():
        raise ValueError('找不到 Qwen Python，请先安装本地模型运行环境并在设置中填写路径')
    model=Path(values['model'])
    required=['config.json','model.safetensors','speech_tokenizer/model.safetensors']
    if any(not (model/name).is_file() or not (model/name).stat().st_size for name in required):
        raise ValueError('Qwen 模型文件不完整，请检查模型目录或重新安装')
    if json.loads((model/'config.json').read_text()).get('tts_model_type')!='custom_voice':
        raise ValueError('请选择 Qwen CustomVoice 模型目录')
    return values


def save(path,cfg):
    cfg=validate(cfg)
    atomic_json(path,cfg)
    Path(path).chmod(0o600)
    return cfg


def signature(cfg):
    cfg=validate(cfg)
    model=Path(cfg['model'])
    stamps=[(name,(model/name).stat().st_size,(model/name).stat().st_mtime_ns) for name in ('model.safetensors','speech_tokenizer/model.safetensors')]
    assets=[(str(path.relative_to(model)),hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(model.rglob('*')) if path.is_file() and path.suffix in ('.json','.txt','.model')]
    runtime=Path(cfg['python']).parent.parent/'lib'
    packages=[(p.parent.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(runtime.glob('python*/site-packages/*dist-info/METADATA')) if p.parent.name.startswith(('mlx_audio-','mlx-','mlx_metal-','transformers-','tokenizers-'))]
    data=dict(config=cfg,weights=stamps,assets=assets,runtime=packages,instruction=INSTRUCTION,revision=1)
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def split_text(text,limit=80):
    """Keep every non-whitespace character, with bounded sentence-sized chunks."""
    if limit<1:
        raise ValueError('分段长度必须大于零')
    result=[];pending=''
    for part in re.findall(r'[^。！？!?\n]+[。！？!?]?|[。！？!?]',text.replace('\n',' ')):
        part=part.strip()
        if not part:continue
        if pending and len(pending)+len(part)>limit:
            result.append(pending);pending=''
        while len(part)>limit:
            cut=part.rfind(' ',0,limit+1)
            if cut<limit//2:cut=limit
            result.append(part[:cut]);part=part[cut:].lstrip()
        pending+=part
    if pending:result.append(pending)
    return result


def check(cfg):
    cfg=validate(cfg)
    if not all(shutil.which(name) for name in ('ffmpeg','ffprobe')):
        raise ValueError('Qwen 导出需要 ffmpeg 与 ffprobe，请先安装')
    result=subprocess.run([cfg['python'],'-B','-c','import mlx.core as mx; import mlx_audio; assert mx.metal.is_available(), "需要 Apple Silicon Mac"'],capture_output=True,text=True,timeout=30)
    if result.returncode:
        raise ValueError('Qwen 运行环境不可用：'+result.stderr[-1500:])
    return dict(message='Qwen 本地模型与 MLX 运行环境可用；生成完全离线。')


def render_wave(speech,output,voice,cfg):
    speaker=voice.removeprefix('qwen:')
    if speaker not in SPEAKERS:
        raise ValueError('不支持的 Qwen 男声')
    cfg=validate(cfg)
    env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'}
    started=time.monotonic()
    result=subprocess.run([cfg['python'],'-B','-m','wechat2podcast.qwen_worker','--model',cfg['model'],'--speaker',speaker,'--input',str(Path(speech).resolve()),'--output',str(Path(output).resolve())],cwd=Path(__file__).resolve().parent.parent,env=env,capture_output=True,text=True,timeout=7200)
    if result.returncode:
        raise ValueError('Qwen 合成未完成，原音频已保留：'+result.stderr[-2000:])
    peak=re.search(r'MLX peak GB: ([0-9.]+)',result.stderr)
    return dict(synthesis_seconds=round(time.monotonic()-started,2),**({'mlx_peak_gb':float(peak[1])} if peak else {}))
