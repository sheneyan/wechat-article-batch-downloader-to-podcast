import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat2podcast import qwen
from wechat2podcast.library import Library, atomic_json


class QwenTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.model=self.root/'model';(self.model/'speech_tokenizer').mkdir(parents=True)
        (self.model/'config.json').write_text(json.dumps({'tts_model_type':'custom_voice'}))
        (self.model/'model.safetensors').write_bytes(b'weights')
        (self.model/'speech_tokenizer/model.safetensors').write_bytes(b'tokenizer')
        self.cfg=dict(python='/usr/bin/python3',model=str(self.model),speed=1.25)

    def test_split_preserves_all_content_and_limits_segments(self):
        text='第一句话。第二句话！\n\n'+('长句没有标点'*40)+'English words and numbers 123.'
        chunks=qwen.split_text(text,80)
        self.assertTrue(all(0<len(s)<=80 for s in chunks))
        self.assertEqual(''.join(''.join(chunks).split()),''.join(text.split()))
        self.assertEqual(qwen.split_text('   '),[])

    def test_invalid_speed_or_incomplete_model_is_rejected(self):
        for speed in [0,3,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):qwen.validate({**self.cfg,'speed':speed})
        (self.model/'speech_tokenizer/model.safetensors').unlink()
        with self.assertRaisesRegex(ValueError,'模型'):qwen.validate(self.cfg)

    def test_saved_config_and_signature_follow_model_speed_changes(self):
        profile=self.root/'tts.json'
        self.assertEqual(qwen.save(profile,self.cfg)['speed'],1.25)
        first=qwen.signature(qwen.load(profile))
        self.assertNotEqual(first,qwen.signature({**self.cfg,'speed':1.5}))
        (self.model/'model.safetensors').write_bytes(b'revised weights')
        self.assertNotEqual(first,qwen.signature(self.cfg))

    def test_tokenizer_or_generation_config_changes_invalidate_cache(self):
        for name in ['generation_config.json','speech_tokenizer/config.json','tokenizer_config.json','vocab.json','merges.txt']:
            with self.subTest(name=name):
                path=self.model/name
                path.write_text('{}')
                before=qwen.signature(self.cfg)
                path.write_text('{"changed":true}')
                self.assertNotEqual(before,qwen.signature(self.cfg))

    def test_qwen_failure_preserves_previous_audio(self):
        from wechat2podcast.audio import render_audio
        speech=self.root/'speech.txt';speech.write_text('正文。')
        output=self.root/'audio.mp3';output.write_bytes(b'previous')
        with patch('wechat2podcast.qwen.render_wave',side_effect=ValueError('Qwen failed')):
            with self.assertRaisesRegex(ValueError,'Qwen failed'):
                render_audio(speech,output,'qwen:Uncle_Fu',180,qwen=self.cfg)
        self.assertEqual(output.read_bytes(),b'previous')
        self.assertEqual(list(self.root.glob('.tts-*')),[])

    def test_qwen_config_change_invalidates_library_cache(self):
        lib=Library(self.root/'library');folder=lib.root/('a'*20);folder.mkdir(parents=True)
        article=dict(id='a'*20,content_sha256='hash',speech='正文。')
        (folder/'audio.mp3').write_bytes(b'previous')
        atomic_json(folder/'audio.json',dict(content_sha256='hash',voice='qwen:Uncle_Fu',rate=180,audio_sha256='same',render_signature=qwen.signature(self.cfg)))
        with patch('wechat2podcast.library.audio_info',return_value={'audio_sha256':'same'}):
            self.assertTrue(lib.render(article,'qwen:Uncle_Fu',qwen=self.cfg)[2])
        with patch('wechat2podcast.library.render_audio',return_value={'audio_sha256':'new'}) as render:
            self.assertFalse(lib.render(article,'qwen:Uncle_Fu',qwen={**self.cfg,'speed':1.5})[2])
            self.assertEqual(render.call_args.kwargs['qwen']['speed'],1.5)
