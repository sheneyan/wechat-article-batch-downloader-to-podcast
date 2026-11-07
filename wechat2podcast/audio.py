"""Generate validated speech audio, keeping intermediate AIFF files temporary."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .remote import sha256_file
from .dependencies import require_audio


def preview_text(text, characters=260):
    if characters < 1:
        raise ValueError('试听字数必须大于零')
    part = text[:characters]
    endings = list(re.finditer(r'[。！？!?]', part))
    return part[:endings[-1].end()] if endings else part


def audio_info(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                             '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    audio = [s for s in data['streams'] if s['codec_type'] == 'audio']
    if len(audio) != 1 or audio[0]['codec_name'] != 'mp3' or audio[0]['sample_rate'] != '24000' or audio[0]['channels'] != 1:
        raise ValueError('音频格式不符合 24 kHz 单声道 MP3')
    duration = float(data['format']['duration'])
    if duration <= 0:
        raise ValueError('音频时长为零')
    digest = sha256_file(path)
    return dict(audio_bytes=Path(path).stat().st_size, audio_sha256=digest,
                audio_file=digest+'.mp3', duration=duration)


def render_audio(speech_path, output, voice='Tingting', rate=180, qwen=None):
    is_qwen=voice.startswith('qwen:')
    if is_qwen:
        from . import qwen as qwen_tts
        qwen=qwen_tts.validate(qwen or qwen_tts.defaults())
    else:
        require_audio(voice)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.tts-', dir=output.parent) as temp:
        temp = Path(temp)
        source=temp/('speech.wav' if is_qwen else 'speech.aiff')
        performance={}
        if is_qwen:
            performance=qwen_tts.render_wave(speech_path,source,voice,qwen)
        else:
            subprocess.run(['/usr/bin/say', '-v', voice, '-r', str(rate), '-f', str(speech_path),
                            '-o', str(source)], check=True, timeout=1800)
        filters=['-af',f"atempo={qwen['speed']}"] if is_qwen else []
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                        '-i', str(source), *filters, '-map', '0:a:0', '-ac', '1', '-ar', '24000',
                        '-c:a', 'libmp3lame', '-b:a', '48k', '-map_metadata', '-1',
                        str(temp/'audio.mp3')], check=True, timeout=600)
        metadata = audio_info(temp/'audio.mp3')
        os.replace(temp/'audio.mp3', output)
    return {**metadata, **performance, 'voice': voice, 'rate': rate, 'engine':'qwen' if is_qwen else 'system',
            **({'render_signature':qwen_tts.signature(qwen),'speed':qwen['speed']} if is_qwen else {})}
