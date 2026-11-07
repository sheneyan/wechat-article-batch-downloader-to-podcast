"""Executed only by the isolated Apple Silicon MLX environment."""
import argparse
import sys
import wave
from pathlib import Path

from .qwen import INSTRUCTION, SPEAKERS, split_text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True);parser.add_argument('--speaker',choices=SPEAKERS,required=True)
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    mx.set_cache_limit(256*1024*1024)
    mx.random.seed(42)
    chunks=split_text(Path(args.input).read_text())
    if not chunks:raise ValueError('没有可朗读的正文')
    model=load_model(args.model)
    max_tokens=1536
    sample_rate=model.sample_rate
    with wave.open(args.output,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(sample_rate)
        for index,text in enumerate(chunks):
            print(f'Qwen {index+1}/{len(chunks)}',file=sys.stderr,flush=True)
            found=False
            for result in model.generate_custom_voice(text=text,speaker=args.speaker,language='Chinese',instruct=INSTRUCTION,max_tokens=max_tokens,verbose=False):
                if result.token_count>=max_tokens:
                    raise ValueError('一段音频达到长度上限，已停止以避免生成不完整正文')
                if result.sample_rate!=sample_rate:raise ValueError('音频采样率不一致')
                audio=np.asarray(result.audio)
                if not audio.size or not np.isfinite(audio).all():raise ValueError('模型返回无效音频')
                output.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
                found=True
                del audio,result
            if not found:raise ValueError('模型没有返回完整音频')
            mx.clear_cache()
    print(f'MLX peak GB: {mx.get_peak_memory()/1e9:.2f}',file=sys.stderr)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
