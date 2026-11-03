"""Pull scripts to a private Mac inbox; never synthesize or publish implicitly."""
import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

from .inbox import normalize
from .library import atomic_json


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        # Never forward the reader's Bearer token to a redirected destination.
        return None


def request(config,path):
    req=urllib.request.Request(config['base_url'].rstrip('/')+path,
                              headers={'Authorization':'Bearer '+config['read_token']})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as response:
        return json.load(response)


def verify_document(doc,expected_sha=None):
    public=normalize({k:doc[k] for k in ('id','title','date','text','notes','source_urls')})
    digest=hashlib.sha256(json.dumps(public,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=doc['sha256'] or (expected_sha is not None and digest!=expected_sha):
        raise ValueError('Script checksum mismatch: '+public['id'])
    return public


def document_stem(identifier):
    return hashlib.sha256(identifier.encode()).hexdigest()


def fetch(config,output,from_start=False):
    identity=hashlib.sha256((config['base_url'].rstrip('/')+'\0'+config['read_token']).encode()).hexdigest()[:24]
    output=Path(output).expanduser()/'sources'/identity
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    documents=output/'documents'
    documents.mkdir(exist_ok=True,mode=0o700)
    state_path=output/'state.json'
    after=0 if from_start or not state_path.exists() else json.loads(state_path.read_text())['cursor']
    count=0
    while True:
        page=request(config,'/v1/scripts?after='+str(after)+'&limit=100')
        for item in page['items']:
            doc=request(config,'/v1/scripts/'+item['id'])
            public=verify_document(doc,item['sha256'])
            name=document_stem(public['id'])
            atomic_json(documents/(name+'.json'),doc)
            for suffix,text in [('.txt',public['text']),('.notes.txt',public['notes'])]:
                dest=documents/(name+suffix)
                temporary=dest.with_suffix(dest.suffix+'.tmp')
                with open(temporary,'w',encoding='utf-8',opener=lambda name,flags:os.open(name,flags,0o600)) as stream:
                    stream.write(text+'\n')
                os.replace(temporary,dest)
            after=doc['seq']
            atomic_json(state_path,dict(cursor=after))
            count+=1
        if not page['has_more']:
            break
    return dict(downloaded=count,cursor=after,output=str(output.resolve()))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='.private/inbox-reader.json')
    parser.add_argument('--output',default='.local/grok-inbox')
    parser.add_argument('--from-start',action='store_true')
    args=parser.parse_args()
    config=json.loads(Path(args.config).expanduser().read_text())
    print(json.dumps(fetch(config,args.output,args.from_start),ensure_ascii=False))


if __name__=='__main__':
    main()
