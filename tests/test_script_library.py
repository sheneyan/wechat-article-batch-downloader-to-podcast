import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wechat2podcast.library import Library
from wechat2podcast.script_library import import_scripts


def script(identifier='daily-x-2026-11-03'):
    doc=dict(id=identifier,title='每日 X 口播',date='2026-11-03',text='今天关注小模型。\n\n第二条新闻。',
             notes='读音备注：不要进入朗读。',source_urls=['https://x.com/example/status/123'])
    payload=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return {**doc,'sha256':hashlib.sha256(payload.encode()).hexdigest(),'seq':2,'created_at':'2026-11-03T04:33:31+00:00'}


class ScriptLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.raw=self.root/'raw'; self.raw.mkdir()
        self.library=Library(self.root/'library')

    def save(self,doc):
        (self.raw/(doc['id']+'.json')).write_text(json.dumps(doc,ensure_ascii=False))
        (self.raw/(doc['id']+'.txt')).write_text(doc['text'])

    def test_import_is_stable_and_only_text_is_spoken(self):
        doc=script(); self.save(doc)
        result=import_scripts(self.library,self.raw)
        self.assertEqual(result['imported'],1)
        article=self.library.articles()[0]
        self.assertEqual(article['speech'],doc['text'])
        self.assertNotIn(doc['notes'],article['speech'])
        self.assertEqual(article['notes'],doc['notes'])
        self.assertEqual(article['source_kind'],'grok')
        self.assertFalse(article['is_test'])
        first=article['id']; (self.library.root/first/'audio.mp3').write_bytes(b'keep')
        import_scripts(self.library,self.raw)
        self.assertEqual(self.library.articles()[0]['id'],first)
        self.assertEqual((self.library.root/first/'audio.mp3').read_bytes(),b'keep')

    def test_connectivity_records_cannot_render_or_publish(self):
        self.save(script('grok-connectivity-2026-11-03-retest'))
        self.assertEqual(import_scripts(self.library,self.raw)['test_count'],1)
        article=self.library.articles()[0]
        with self.assertRaisesRegex(ValueError,'测试稿'):
            self.library.render(article)
        with self.assertRaisesRegex(ValueError,'测试稿'):
            self.library.publishable(article)

    def test_corrupt_source_is_not_imported(self):
        doc=script(); self.save({**doc,'text':'被篡改的正文'})
        with self.assertRaisesRegex(ValueError,'checksum'):
            import_scripts(self.library,self.raw)
        self.assertEqual(self.library.articles(),[])

    def test_same_id_from_other_service_cannot_replace_saved_content(self):
        original=script();self.save(original);import_scripts(self.library,self.raw)
        before=self.library.articles()[0]
        other=self.root/'other';other.mkdir()
        changed={k:original[k] for k in ('id','title','date','text','notes','source_urls')}
        changed['text']='其他服务上的不同正文。'
        changed['sha256']=hashlib.sha256(json.dumps(changed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        (other/'document.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'编号冲突'):
            import_scripts(self.library,other)
        self.assertEqual(self.library.articles()[0],before)


if __name__=='__main__':
    unittest.main()
