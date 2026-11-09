"""Download a pinned public encoder, never historical v1 or new task weights."""
import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MODEL="monologg/koelectra-base-v3-discriminator"
REVISION="68b30cd259f34a4b5aa8786392612ba2a2617fcc"
REPORTS=ROOT/"reports/v2_experiment_design"
CACHE=ROOT/"artifacts/v2_experiment_assets/hf/hub"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download",action="store_true")
    args=parser.parse_args()
    os.environ.update(HF_HUB_DISABLE_TELEMETRY="1",HF_HUB_DISABLE_XET="1")
    from huggingface_hub import model_info,hf_hub_download
    report=dict(model=MODEL,revision=REVISION,public_pretrained_encoder_only=True,
                original_v1_checkpoint_restored=False,training_executed=False)
    try:
        info=model_info(MODEL,revision=REVISION,files_metadata=True,token=False,timeout=30)
        assert info.sha==REVISION
        siblings={s.rfilename:s for s in info.siblings}
        report["remote_files"]=[dict(name=s.rfilename,size=s.size,blob_id=s.blob_id,
            lfs=dataclasses.asdict(s.lfs) if dataclasses.is_dataclass(s.lfs) else s.lfs) for s in info.siblings]
        report["files"]=[]
        if args.download:
            for name in ("config.json","tokenizer_config.json","vocab.txt","pytorch_model.bin"):
                print(f"Preparing public base asset: {name}",flush=True)
                target=Path(hf_hub_download(MODEL,name,revision=REVISION,cache_dir=str(CACHE),token=False))
                h=hashlib.sha256()
                with target.open("rb") as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
                row=dict(path=str(target),name=name,bytes=target.stat().st_size,sha256=h.hexdigest())
                expected=siblings[name]
                assert row["bytes"]==expected.size
                if expected.lfs:
                    expected_sha=expected.lfs.sha256 if hasattr(expected.lfs,"sha256") else expected.lfs["sha256"]
                    assert row["sha256"]==expected_sha
                    row["matches_remote_lfs_sha256"]=True
                else:
                    data=target.read_bytes()
                    assert hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==expected.blob_id
                    row["matches_remote_git_blob"]=True
                report["files"].append(row)
        report["status"]="READY_PUBLIC_BASE_ASSETS" if args.download else "READY_REMOTE_METADATA_ONLY"
    except Exception as error:
        import traceback
        report.update(status="BLOCKED_PUBLIC_BASE_ASSETS",exception=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    REPORTS.mkdir(parents=True,exist_ok=True)
    (REPORTS/"public_base_assets.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("remote_files","traceback")},ensure_ascii=False,indent=2))
    return int(report["status"].startswith("BLOCKED"))


if __name__=="__main__":raise SystemExit(main())
