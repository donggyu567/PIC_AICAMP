"""Prepare user-authorized lossless parts within the connector file limit."""
import hashlib
from pathlib import Path
import shutil
from .src.common import V3,create_json,read_json,require,sha
from .join_model import join


if __name__=='__main__':
    source=V3/'handoff/research_20261117_v1/models/v3_seed42_inference.pt'
    out=V3/'transfer_20261117_v1';out.mkdir(exist_ok=False)
    parts=[];offset=0
    with source.open('rb') as stream:
        for i in range(1,100):
            block=stream.read(64*1024*1024)
            if not block:break
            name=f'v3_seed42_inference.pt.part{i:04d}'
            with (out/name).open('xb') as f:f.write(block)
            parts.append(dict(index=i,name=name,offset=offset,bytes=len(block),sha256=hashlib.sha256(block).hexdigest(),md5=hashlib.md5(block).hexdigest()))
            offset+=len(block)
    require(offset==source.stat().st_size,'Split byte count mismatch')
    m=dict(schema='lossless-model-parts/1',original_name='v3_seed42_inference.pt',bytes=offset,sha256=sha(source),
        parts=parts,reason='Official connector pre-invocation materialization limit100MiB; each ordinary file64MiB or less, as explicitly allowed by user',
        human_reviewed=False,purpose='internal_experiment',deployment_allowed=False)
    create_json(out/'TRANSFER_MANIFEST.local.json',m)
    shutil.copyfile(V3/'join_model.py',out/'join_model.py')
    verification=join(out/'TRANSFER_MANIFEST.local.json',out/'verified_reassembly.pt')
    require(verification['sha256']==m['sha256'],'Local split/rejoin changed bytes')
    verified=(out/'verified_reassembly.pt').resolve();require(verified.parent==out.resolve(),'Unsafe cleanup target')
    verified.unlink()  # Only this newly created, verified temporary duplicate.
    create_json(out/'local_reassembly_verification.json',verification)
    print('PARTS',len(parts),'FULL SHA',m['sha256'],'TOTAL',offset)
