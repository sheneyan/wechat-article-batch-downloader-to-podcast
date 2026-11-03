import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path

from wechat2podcast.inbox import make_server


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server=make_server(('127.0.0.1',0),Path(self.tmp.name)/'inbox.sqlite3','writer-secret','reader-secret')
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.doc=dict(id='daily-x-2026-11-03',title='每日 X 口播',date='2026-11-03',text='今天关注小模型。',notes='读音备注独立保存。')

    def call(self,path,token=None,doc=None):
        headers={'Content-Type':'application/json'}
        if token: headers['Authorization']='Bearer '+token
        request=urllib.request.Request(self.base+path,data=json.dumps(doc,ensure_ascii=False).encode() if doc is not None else None,headers=headers)
        try:
            response=urllib.request.urlopen(request,timeout=5)
        except urllib.error.HTTPError as exc:
            response=exc
        with response:
            return response.status,json.load(response)

    def test_health_is_readable_but_writes_require_auth(self):
        self.assertEqual(self.call('/healthz')[0],200)
        self.assertEqual(self.call('/v1/scripts',doc=self.doc)[0],401)
        self.assertEqual(self.call('/v1/scripts','reader-secret',self.doc)[0],401)

    def test_save_receipt_and_reader_retrieval(self):
        code,receipt=self.call('/v1/scripts','writer-secret',self.doc)
        self.assertEqual(code,201)
        self.assertTrue(receipt['stored'])
        self.assertEqual(self.call('/v1/scripts/'+self.doc['id'],'writer-secret')[0],401)
        code,saved=self.call('/v1/scripts/'+self.doc['id'],'reader-secret')
        self.assertEqual(code,200)
        self.assertEqual(saved['text'],self.doc['text'])
        self.assertEqual(saved['notes'],self.doc['notes'])
        self.assertEqual(len(saved['sha256']),64)

    def test_duplicate_is_idempotent_and_edit_cannot_overwrite(self):
        self.call('/v1/scripts','writer-secret',self.doc)
        code,receipt=self.call('/v1/scripts','writer-secret',self.doc)
        self.assertEqual(code,200)
        self.assertTrue(receipt['duplicate'])
        self.assertEqual(self.call('/v1/scripts','writer-secret',{**self.doc,'text':'不同版本'})[0],409)
        self.assertEqual(self.call('/v1/scripts/'+self.doc['id'],'reader-secret')[1]['text'],self.doc['text'])

    def test_incremental_list_does_not_include_text(self):
        self.call('/v1/scripts','writer-secret',self.doc)
        self.call('/v1/scripts','writer-secret',{**self.doc,'id':'daily-x-2026-11-04','date':'2026-11-04'})
        code,page=self.call('/v1/scripts?after=0&limit=1','reader-secret')
        self.assertEqual(code,200)
        self.assertEqual(len(page['items']),1)
        self.assertNotIn('text',page['items'][0])
        self.assertTrue(page['has_more'])
        following=self.call('/v1/scripts?after='+str(page['next_cursor']),'reader-secret')[1]
        self.assertEqual(following['items'][0]['id'],'daily-x-2026-11-04')

    def test_bad_payload_does_not_crash_service(self):
        for doc in [[],{**self.doc,'text':''},{**self.doc,'date':'bad'},{**self.doc,'id':'../escape'}]:
            self.assertEqual(self.call('/v1/scripts','writer-secret',doc)[0],400)
        self.assertEqual(self.call('/healthz')[0],200)

    def test_non_json_content_and_unsupported_method_rejected(self):
        request=urllib.request.Request(self.base+'/v1/scripts',data=b'hello',headers={'Authorization':'Bearer writer-secret','Content-Type':'text/plain'})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code,415)

    def test_mac_fetch_keeps_notes_separate_and_retries_without_duplicates(self):
        from wechat2podcast.inbox_client import fetch
        self.call('/v1/scripts','writer-secret',self.doc)
        output=Path(self.tmp.name)/'mac-inbox'
        config=dict(base_url=self.base,read_token='reader-secret')
        self.assertEqual(fetch(config,output)['downloaded'],1)
        self.assertEqual((output/(self.doc['id']+'.txt')).read_text().strip(),self.doc['text'])
        self.assertEqual((output/(self.doc['id']+'.notes.txt')).read_text().strip(),self.doc['notes'])
        self.assertEqual(fetch(config,output)['downloaded'],0)

    def test_receipt_is_available_to_writer_without_disclosing_text(self):
        self.call('/v1/scripts','writer-secret',self.doc)
        code,receipt=self.call('/v1/receipts/'+self.doc['id'],'writer-secret')
        self.assertEqual(code,200)
        self.assertEqual(receipt['id'],self.doc['id'])
        self.assertNotIn('text',receipt)


if __name__=='__main__':
    unittest.main()
