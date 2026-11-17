# Drive 분할 전송·권한 상태

2026-11-18 읽기 전용 복구 확인. **7개 분할 업로드와 전체 무손실 재조립 검증은 완료, 단일 .pt 원격 업로드와 팀원 권한 부여는 미완료**다. 이번 복구에서 파일 이동·신규 공유·공개 권한 변경·공유 재시도를 하지 않았다.

새 [소유자 전용 폴더](https://drive.google.com/drive/folders/1DU7m-PFLrE7rF_h9UwiaH1BgTUuB_K-m)를 사용했다. 기존 팀 폴더의 링크 보유자 편집 권한으로 가중치를 옮기지 않았다. 아래 링크는 실제 업로드 응답과 오늘의 폴더 목록에서 확인했으며 팀원 접근 가능 링크라고 주장하지 않는다.

| 순서 | 파일 | bytes | 조각 SHA-256 | 실제 Drive URL |
|---|---|---:|---|---|
| 1 | `v3_seed42_inference.pt.part0001` | 67,108,864 | `c49978142aa2d0847773bf661b0866d275e493329789ac43dee6c12ae8819f1a` | [소유자 전용 파일](https://drive.google.com/file/d/1PhXEyiz0sYb6VWqPLwZT1e1rl8M49z1i/view?usp=drivesdk) |
| 2 | `v3_seed42_inference.pt.part0002` | 67,108,864 | `101f5c63c9610ce47a3a59a58c796940db6c4bd097cefe69b07c645797bfdfa8` | [소유자 전용 파일](https://drive.google.com/file/d/1HHtz4pVX8uRc9YxvFAzdlczYh_39fX5A/view?usp=drivesdk) |
| 3 | `v3_seed42_inference.pt.part0003` | 67,108,864 | `86451e18df684f8def7e3f08283f080072c641487d2437d3d5af0862ce58031e` | [소유자 전용 파일](https://drive.google.com/file/d/1vFps2flb4LrqsklJ6zMN7Hax4L9ZPKYn/view?usp=drivesdk) |
| 4 | `v3_seed42_inference.pt.part0004` | 67,108,864 | `dd1a4ab9f5a25e4740e995c9f1c38688980f8d05acca264b1486963839e6485e` | [소유자 전용 파일](https://drive.google.com/file/d/1gQRdyDmvUH4tii0mXPw_KnMn_8uGosgQ/view?usp=drivesdk) |
| 5 | `v3_seed42_inference.pt.part0005` | 67,108,864 | `f80db16310dda931b4381c7ceed1916f09dfc0bbd3e39d2a6e8a0344b2fcc8a7` | [소유자 전용 파일](https://drive.google.com/file/d/1BBb1SnJvQ2CF8rGQJLadr_NBi_rSyJco/view?usp=drivesdk) |
| 6 | `v3_seed42_inference.pt.part0006` | 67,108,864 | `81a9f15cf195c7e3e999ab8c7505ad66c2d42f0368a24865b273ec446a59a9ce` | [소유자 전용 파일](https://drive.google.com/file/d/1FF7OiSzm23qPE2dSkfh3GmCQQrEm1kPR/view?usp=drivesdk) |
| 7 | `v3_seed42_inference.pt.part0007` | 46,785,312 | `ba7755a4094fba792f8c139e683e5b05d535ddefa8bccc3132b8651d72554dec` | [소유자 전용 파일](https://drive.google.com/file/d/1SS3Va4b-X6Ad_YmCFG6lTsu5hbm2YZ-i/view?usp=drivesdk) |

각 조각을 실제로 재다운로드한 뒤 원래 순서로 재조립했다. 전체449,438,496bytes의 SHA는 `35dae5286fb4f39f23821989da6e3afcee5d9827197969e6ec88d09e47d083c2`로 원본 추론 모델과 일치했다. 첫 조각은 ZIP MIME으로 보일 수 있으나 압축을 풀지 말고 그대로 재조립한다.

단일 파일 전송은 연결의100MiB 준비 한도에서 거부됐다. 사용자 지침에 허용된64MiB 이하7개 일반 파일로 전송했으며 크기/보안 제한이나 ACL을 변경하지 않았다. 실제 완성 모델의 단일 원격 URL은 없다. 재조립 도구와 비민감 manifest는 이 디렉터리의 join_model.py/TRANSFER_MANIFEST.json으로 Git에 제공한다. 중단 시점의 소형 추가 업로드는 원격 목록에 없으므로 업로드 완료로 표시하지 않는다.

```powershell
python join_model.py --manifest TRANSFER_MANIFEST.json --output models/v3_seed42_inference.pt
```

외부 공유는 자동 승인 검토에서 특정 수신자와 비공개 모델 payload에 대한 명시적 승인이 없다는 이유로 거부됐다. 현재 파일은 소유자 전용이다. 공유 진단 원문·개인 계정·서명 다운로드 URL은 공개하지 않는다. 팀원 접근에는 수신자·대상 파일·권한을 명시한 별도 승인이 필요하며, 이번 복구 지침에 따라 재시도하지 않았다.
