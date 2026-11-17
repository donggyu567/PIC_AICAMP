"""Lossless ordinary-file reassembly with per-part and full SHA-256 checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path

def require(condition,message):
    if not condition:raise ValueError(message)


def join(manifest_path,output):
    path=Path(manifest_path).resolve();m=json.loads(path.read_text(encoding='utf-8-sig'))
    require(m['schema']=='lossless-model-parts/1','Wrong transfer schema')
    target=Path(output).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise FileExistsError(target)
    temp=target.with_name(target.name+'.partial')
    total=hashlib.sha256();size=0
    with temp.open('xb') as stream:
        for index,part in enumerate(m['parts'],1):
            require(part['index']==index and Path(part['name']).name==part['name'],'Unsafe part name/order')
            source=(path.parent/part['name']).resolve();require(source.parent==path.parent,'Part escapes transfer directory')
            check=hashlib.sha256();n=0
            with source.open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''):
                    check.update(block);total.update(block);stream.write(block);n+=len(block);size+=len(block)
            require(n==part['bytes'] and check.hexdigest()==part['sha256'],'Part mismatch: '+part['name'])
        stream.flush();os.fsync(stream.fileno())
    require(size==m['bytes'] and total.hexdigest()==m['sha256'],'Full model mismatch')
    os.rename(temp,target)
    return dict(path=str(target),bytes=size,sha256=total.hexdigest(),parts=len(m['parts']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',default='TRANSFER_MANIFEST.json');p.add_argument('--output',default='v3_seed42_inference.pt')
    args=p.parse_args();print(json.dumps(join(args.manifest,args.output),indent=2))
