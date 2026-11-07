import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from wechat2podcast.library import Library, atomic_json
from wechat2podcast.script_library import import_scripts
from wechat2podcast.gui import handle


class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.lib=Library(self.root/'library')
        self.archive=self.root/'archive';self.archive.mkdir()
        (self.archive/'a.md').write_text('原始正文。')
        (self.archive/'style_corpus.jsonl').write_text(json.dumps(dict(title='文章',author='作者',url='https://mp.weixin.qq.com/s/a',publish_time='',markdown_path='a.md')))

    def test_delete_files_and_scanning_never_restores_record(self):
        a=self.lib.scan(self.archive)[0]; aid=a['id']
        folder=self.lib.root/aid
        (folder/'audio.mp3').write_bytes(b'audio');(folder/'speech.txt').write_text('正文')
        preview=self.lib.root.parent/'previews'/aid;preview.mkdir(parents=True);(preview/'audio.mp3').write_bytes(b'preview')
        result=handle(dict(action='delete_articles',library=str(self.lib.root),config=str(self.root/'unused.json'),ids=[aid]))
        self.assertEqual(result['articles'],[])
        self.assertFalse(folder.exists());self.assertFalse(preview.exists())
        self.assertEqual(Library(self.lib.root).scan(self.archive),[])
        self.assertTrue((self.archive/'a.md').exists())

    def test_deleted_grok_is_not_reimported(self):
        raw=self.root/'raw';raw.mkdir()
        doc=dict(id='daily-x-2026-11-08',title='每日 X',date='2026-11-08',text='正文',notes='',source_urls=[])
        doc['sha256']=hashlib.sha256(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        (raw/'doc.json').write_text(json.dumps(doc));import_scripts(self.lib,raw)
        aid=self.lib.articles()[0]['id']
        self.assertTrue(hasattr(self.lib,'delete_articles'),'Library must support explicit deletion')
        self.lib.delete_articles([aid])
        self.assertEqual(import_scripts(Library(self.lib.root),raw)['imported'],0)
        self.assertEqual(self.lib.articles(),[])

    def test_invalid_batch_cannot_remove_valid_article(self):
        aid=self.lib.scan(self.archive)[0]['id']
        self.assertTrue(hasattr(self.lib,'delete_articles'),'Library must support explicit deletion')
        with self.assertRaises(ValueError):self.lib.delete_articles([aid,'../../outside'])
        self.assertEqual(len(self.lib.articles()),1)

    def test_symlink_cannot_delete_outside_library(self):
        aid=self.lib.scan(self.archive)[0]['id'];folder=self.lib.root/aid
        outside=self.root/'outside';folder.rename(outside);folder.symlink_to(outside,target_is_directory=True)
        self.assertTrue(hasattr(self.lib,'delete_articles'),'Library must support explicit deletion')
        with self.assertRaises(ValueError):self.lib.delete_articles([aid])
        self.assertTrue((outside/'article.json').exists())

class VoiceTests(unittest.TestCase):
    def test_installed_voice_names_keep_spaces_and_language(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from wechat2podcast import dependencies
        self.assertTrue(hasattr(dependencies,'system_voices'),'Must expose installed voices to the picker')
        with patch('wechat2podcast.dependencies.subprocess.run',return_value=SimpleNamespace(stdout='Tingting    zh_CN  # 你好\nEddy (中文（中国大陆）)    zh_CN  # 你好\nDaniel    en_GB  # Hello\n')):
            voices=dependencies.system_voices()
        self.assertEqual([v['id'] for v in voices],['Tingting','Eddy (中文（中国大陆）)','Daniel'])
        self.assertEqual(voices[0]['language'],'zh_CN')
