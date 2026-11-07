import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType,SimpleNamespace
from unittest.mock import patch

from wechat2podcast.qwen_worker import main


class WorkerTests(unittest.TestCase):
    def run_worker(self,results):
        model=SimpleNamespace(sample_rate=24000,generate_custom_voice=lambda **kw:iter(results))
        mx=ModuleType('mlx.core');mx.set_cache_limit=lambda n:None;mx.random=SimpleNamespace(seed=lambda n:None)
        mx.clear_cache=lambda:None;mx.get_peak_memory=lambda:0
        mlx=ModuleType('mlx');mlx.core=mx
        utils=ModuleType('mlx_audio.tts.utils');utils.load_model=lambda path:model
        np=ModuleType('numpy');np.asarray=lambda x:x;np.isfinite=lambda x:SimpleNamespace(all=lambda:False)
        modules={'mlx':mlx,'mlx.core':mx,'mlx_audio':ModuleType('mlx_audio'),'mlx_audio.tts':ModuleType('mlx_audio.tts'),'mlx_audio.tts.utils':utils,'numpy':np}
        with tempfile.TemporaryDirectory() as tmp:
            text=Path(tmp)/'text.txt';text.write_text('正文。')
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['worker','--model',tmp,'--speaker','Uncle_Fu','--input',str(text),'--output',str(Path(tmp)/'out.wav')]):
                main()

    def test_generation_limit_is_an_error_instead_of_truncated_success(self):
        with self.assertRaisesRegex(ValueError,'长度上限'):
            self.run_worker([SimpleNamespace(token_count=1536)])

    def test_empty_generation_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'没有返回'):
            self.run_worker([])

    def test_nonfinite_waveform_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'无效音频'):
            self.run_worker([SimpleNamespace(token_count=3,sample_rate=24000,audio=SimpleNamespace(size=1))])
