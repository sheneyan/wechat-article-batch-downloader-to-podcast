import tempfile
import unittest
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch
from test_script_library import script
from wechat2podcast.inbox_client import fetch,request as http_request
from wechat2podcast.script_library import import_scripts
from wechat2podcast.library import Library


class InboxStorageTests(unittest.TestCase):
    def response(self,documents):
        def request(config,path):
            doc=documents[config['base_url']]
            if '?' in path:
                after=int(parse_qs(urlsplit(path).query)['after'][0])
                items=[] if after>=doc['seq'] else [{k:doc[k] for k in ('id','seq','sha256')}]
                return dict(items=items,has_more=False,next_cursor=doc['seq'])
            return doc
        return request

    def test_switching_service_cannot_reuse_old_service_cursor(self):
        old={**script('old-script'),'seq':100}
        new={**script('new-script'),'seq':1}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('wechat2podcast.inbox_client.request',side_effect=self.response({'https://old':old,'https://new':new})):
                output=Path(tmp)/'cache'
                self.assertEqual(fetch(dict(base_url='https://old',read_token='a'*64),output)['downloaded'],1)
                self.assertEqual(fetch(dict(base_url='https://new',read_token='b'*64),output)['downloaded'],1)

    def test_valid_state_id_is_not_overwritten_by_cursor(self):
        doc=script('state')
        with tempfile.TemporaryDirectory() as tmp:
            with patch('wechat2podcast.inbox_client.request',side_effect=self.response({'https://service':doc})):
                result=fetch(dict(base_url='https://service',read_token='a'*64),Path(tmp)/'cache')
            library=Library(Path(tmp)/'library')
            self.assertEqual(import_scripts(library,Path(result['output']))['imported'],1)
            self.assertEqual(library.articles()[0]['source_id'],'state')

    def test_case_variant_ids_have_distinct_local_files(self):
        docs={d['id']:d for d in [{**script('Daily-X'),'seq':1},{**script('daily-x'),'seq':2}]}
        def request(config,path):
            if '?' in path:
                return dict(items=[{k:d[k] for k in ('id','seq','sha256')} for d in docs.values()],has_more=False)
            return docs[path.rsplit('/',1)[-1]]
        with tempfile.TemporaryDirectory() as tmp,patch('wechat2podcast.inbox_client.request',side_effect=request):
            result=fetch(dict(base_url='https://service',read_token='a'*64),Path(tmp)/'cache')
            library=Library(Path(tmp)/'library')
            self.assertEqual(import_scripts(library,Path(result['output']))['imported'],2)
            self.assertEqual({a['source_id'] for a in library.articles()},set(docs))

    def test_reader_does_not_follow_redirects_with_bearer_token(self):
        reached=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location','/target');self.end_headers()
                else:
                    reached.append(self.headers.get('Authorization'))
                    self.send_response(200);self.end_headers();self.wfile.write(b'{}')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            http_request(dict(base_url='http://127.0.0.1:'+str(server.server_port),read_token='a'*64),'/redirect')
        self.assertEqual(ctx.exception.code,302)
        self.assertEqual(reached,[])


if __name__=='__main__':
    unittest.main()
