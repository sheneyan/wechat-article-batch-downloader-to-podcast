"""Authenticated text-only intake, independent of podcast audio publication."""
import argparse
import hashlib
import hmac
import json
import re
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_BODY=256*1024
MAX_RECORDS=10000
MAX_STORED_BYTES=128*1024*1024
ID_PATTERN=r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}'


class Rejected(Exception):
    def __init__(self,status,message):
        self.status=status
        self.message=message


def normalize(doc):
    if not isinstance(doc,dict):
        raise ValueError('JSON body must be an object')
    if set(doc)-{'id','title','date','text','notes','source_urls'}:
        raise ValueError('Allowed fields: id, title, date, text, notes, source_urls')
    for field,limit in [('title',200),('date',10),('text',50000),('notes',20000)]:
        value=doc.get(field,'' if field=='notes' else None)
        if not isinstance(value,str) or len(value)>limit or (field!='notes' and not value.strip()):
            raise ValueError('Invalid or missing field: '+field)
    day=doc['date'].strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):
        raise ValueError('date must be YYYY-MM-DD')
    date.fromisoformat(day)
    identifier=doc.get('id','daily-x-'+day)
    if not isinstance(identifier,str) or not re.fullmatch(ID_PATTERN,identifier):
        raise ValueError('id must contain 1-100 letters, digits, dots, underscores or hyphens')
    urls=doc.get('source_urls',[])
    if not isinstance(urls,list) or len(urls)>100:
        raise ValueError('source_urls must be an array of at most 100 URLs')
    for url in urls:
        if not isinstance(url,str) or len(url)>2048:
            raise ValueError('Invalid source URL')
        parts=urlsplit(url)
        if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:
            raise ValueError('Source URLs must be HTTP(S) without credentials')
    return dict(id=identifier,title=doc['title'].strip(),date=day,text=doc['text'].strip(),
                notes=doc.get('notes','').strip(),source_urls=urls)


class Store:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS scripts (seq INTEGER PRIMARY KEY AUTOINCREMENT, '
                       'id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL, '
                       'created_at TEXT NOT NULL, size INTEGER NOT NULL)')
            db.commit()
        self.path.chmod(0o600)

    @staticmethod
    def receipt(row,duplicate=False):
        return dict(stored=True,id=row[1],seq=row[0],sha256=row[3],created_at=row[4],bytes=row[5],duplicate=duplicate)

    def save(self,doc):
        payload=json.dumps(normalize(doc),ensure_ascii=False,sort_keys=True,separators=(',',':'))
        normalized=json.loads(payload)
        digest=hashlib.sha256(payload.encode()).hexdigest()
        with closing(sqlite3.connect(self.path,timeout=10)) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM scripts WHERE id=?',(normalized['id'],)).fetchone()
            if row:
                if row[3]!=digest:
                    raise Rejected(409,'ID already exists with different content; use a revision ID such as -v2')
                return 200,self.receipt(row,True)
            count,size=db.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM scripts').fetchone()
            if count>=MAX_RECORDS or size+len(payload.encode())>MAX_STORED_BYTES:
                raise Rejected(507,'Text inbox quota reached')
            created=datetime.now(timezone.utc).isoformat(timespec='seconds')
            cursor=db.execute('INSERT INTO scripts(id,payload,sha256,created_at,size) VALUES(?,?,?,?,?)',
                              (normalized['id'],payload,digest,created,len(payload.encode())))
            db.commit()
            return 201,self.receipt((cursor.lastrowid,normalized['id'],payload,digest,created,len(payload.encode())))

    def get(self,identifier,receipt=False):
        with closing(sqlite3.connect(self.path,timeout=10)) as db:
            row=db.execute('SELECT * FROM scripts WHERE id=?',(identifier,)).fetchone()
        if not row:
            raise Rejected(404,'Script not found')
        if receipt:
            return self.receipt(row)
        return {**json.loads(row[2]),'seq':row[0],'sha256':row[3],'created_at':row[4]}

    def page(self,after,limit):
        with closing(sqlite3.connect(self.path,timeout=10)) as db:
            rows=db.execute('SELECT * FROM scripts WHERE seq>? ORDER BY seq LIMIT ?',(after,limit+1)).fetchall()
        items=[]
        for row in rows[:limit]:
            doc=json.loads(row[2])
            items.append({**{k:doc[k] for k in ('id','title','date')},'seq':row[0],
                          'sha256':row[3],'created_at':row[4],'bytes':row[5]})
        return dict(items=items,next_cursor=items[-1]['seq'] if items else after,has_more=len(rows)>limit)


def make_server(address,database,writer_token,reader_token):
    if not writer_token or not reader_token or writer_token==reader_token:
        raise ValueError('Distinct nonempty write/read tokens are required')
    store=Store(database)

    class Handler(BaseHTTPRequestHandler):
        server_version='ScriptInbox/1'
        sys_version=''

        def log_message(self,*args):
            pass

        def reply(self,status,data):
            body=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Connection','close')
            self.end_headers()
            self.close_connection=True
            self.wfile.write(body)

        def authorize(self,token):
            supplied=self.headers.get('Authorization','')
            if not hmac.compare_digest(supplied.encode(),('Bearer '+token).encode()):
                raise Rejected(401,'Valid Bearer token required')

        def dispatch(self,write=False):
            try:
                url=urlsplit(self.path)
                path=url.path
                if not write and path=='/healthz':
                    return self.reply(200,dict(status='ok',service='script-inbox',version=1))
                if write:
                    self.authorize(writer_token)
                    if path!='/v1/scripts':
                        raise Rejected(404,'Not found')
                    if self.headers.get_content_type()!='application/json':
                        raise Rejected(415,'Content-Type must be application/json')
                    if self.headers.get('Transfer-Encoding'):
                        raise Rejected(400,'Chunked request bodies are not supported')
                    length=int(self.headers.get('Content-Length','0'))
                    if length<=0:
                        raise Rejected(400,'A JSON body is required')
                    if length>MAX_BODY:
                        raise Rejected(413,'Request body exceeds 256 KiB')
                    self.connection.settimeout(15)
                    body=self.rfile.read(length)
                    if len(body)!=length:
                        raise Rejected(400,'Incomplete request body')
                    status,receipt=store.save(json.loads(body.decode('utf-8')))
                    return self.reply(status,receipt)
                if path.startswith('/v1/receipts/'):
                    self.authorize(writer_token)
                    identifier=path.removeprefix('/v1/receipts/')
                    if not re.fullmatch(ID_PATTERN,identifier):
                        raise Rejected(400,'Invalid ID')
                    return self.reply(200,store.get(identifier,receipt=True))
                self.authorize(reader_token)
                if path=='/v1/scripts':
                    query=parse_qs(url.query)
                    after=int(query.get('after',['0'])[0])
                    limit=int(query.get('limit',['50'])[0])
                    if after<0 or not 1<=limit<=100:
                        raise ValueError('after must be >=0; limit must be 1-100')
                    return self.reply(200,store.page(after,limit))
                if path.startswith('/v1/scripts/'):
                    identifier=path.removeprefix('/v1/scripts/')
                    if not re.fullmatch(ID_PATTERN,identifier):
                        raise Rejected(400,'Invalid ID')
                    return self.reply(200,store.get(identifier))
                raise Rejected(404,'Not found')
            except Rejected as exc:
                self.reply(exc.status,dict(error=exc.message))
            except (ValueError,UnicodeError) as exc:
                self.reply(400,dict(error=str(exc)))
            except sqlite3.Error:
                self.reply(503,dict(error='Storage temporarily unavailable'))
            except TimeoutError:
                self.reply(408,dict(error='Request timed out'))

        def do_POST(self):
            self.dispatch(write=True)

        def do_GET(self):
            self.dispatch()

    return ThreadingHTTPServer(address,Handler)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text())
    server=make_server(('127.0.0.1',cfg.get('port',18769)),cfg['database'],cfg['write_token'],cfg['read_token'])
    server.serve_forever()


if __name__=='__main__':
    main()
