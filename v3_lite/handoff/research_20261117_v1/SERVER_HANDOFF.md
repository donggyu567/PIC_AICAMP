# KoELECTRA v3 Lite — 연구용 CPU 모델 인계

**실제 학습·저장·독립 CPU 재로딩 완료. v2 대체 후보 채택은 하지 않음. 실서버/운영 검증 미완료.**

같은 신규 합성 VALIDATION에서 위험 F1은0.7563→0.8276, 정상 대화FP는6/12→3/12, 정보탐색 TP는0→5였다. 개인정보 F1은0.4375→0.4211, AP는0.5754→0.4790으로 악화돼 사전 개선 gate에 미달했다. 따라서 이 패키지는 보존·검토용 연구 모델이며 운영 전환 권고가 아니다. epoch2 진행 조건도 실패해 추가 학습하지 않았다.

## 파일과 설치

- inference `models/v3_seed42_inference.pt`:449,438,496bytes, SHA-256 `35dae5286fb4f39f23821989da6e3afcee5d9827197969e6ec88d09e47d083c2`
- training:1,348,303,402bytes, SHA-256 `607005ca8ce0e5a1352b4624eb49eab44f66015af58487396fe5b815cc9bfda9`; 로컬 run 폴더에 optimizer와 함께 보존.
- bundle_manifest.json SHA-256 `a19714bd1d23b2e61bc855cdcc4752c3776b86cf47d5bd1b189eb53bb3c74751`
- 검증 환경: Windows/Python3.11.16,torch2.6.0+cpu,transformers4.57.6. 나머지는 requirements-tested.txt. 다른 OS/서버 호환성은 미확인이다.

runtime.py/core_runtime.py/vendor/tokenizer/manifest를 같은 구조로 배치한다. Drive 연결이100MiB 파일 한도로 단일 모델을 거부했으므로 모델은64MiB 이하7개 조각과 TRANSFER_MANIFEST.json/join_model.py로 전달한다. 모든 조각을 같은 디렉터리에 내려받은 후 아래처럼 **새 파일**로 재조립한다. 기존 모델은 덮어쓰지 않는다.

```powershell
python join_model.py --manifest TRANSFER_MANIFEST.json --output models/v3_seed42_inference.pt
python runtime.py --bundle . --manifest-sha a19714bd1d23b2e61bc855cdcc4752c3776b86cf47d5bd1b189eb53bb3c74751
```

join_model.py는 순서·조각별 크기/SHA와 전체 SHA를 확인한다. 분할은 바이트 보존이며 양자화/압축/모델 변경이 아니다. 추론 파일은 실제 optimizer buffers를 제외해 학습 파일의 약1/3이 됐다. 기존 v1 envelope 호환성을 위한 optimizer_state_dict={} 빈 키만 남겼다.

## 입력·출력

```json
{"history_texts":[],"current_text":"공개 안내문을 확인하겠습니다."}
```

입력은 이전 최대5발화와 현재 발화,512token,[CLS] history [SEP] current [SEP],history 줄바꿈,segment0/1,right padding이다. 오래된 history 전체를 제거하며 현재만으로 초과하면422다. 전사·마스킹·ASR 교정은 제공하지 않는다.

Python API:

```python
from runtime import V3Predictor, serve_request
p = V3Predictor('.', expected_manifest_sha='a19714bd1d23b2e61bc855cdcc4752c3776b86cf47d5bd1b189eb53bb3c74751')
response = serve_request(p, {'history_texts': [], 'current_text': '공개 안내문을 확인하겠습니다.'})
```

성공은 ok=true/result 객체다. result의 risk_probability는 risk head의 sigmoid1회, risk_score는 그 값×100, is_phishing은0.5판정이다. 실제 피해 발생확률로 보정된 값이 아니다. type_probabilities는 canonical8종 독립 sigmoid이며 합이1일 필요가 없다. risk와 type은 독립 head다. 서버가 sigmoid를 다시 적용하면 안 된다.

label순서: institution_impersonation, money_transfer, personal_information, app_installation, secrecy, threat_pressure, loan_fraud, information_probing. 의미는 각각 기관사칭,금전이전 유도,정확한 개인정보 직접수집,앱 설치/실행 유도,제3자에게 숨기도록 요구,불이익을 통한 강요,허위 대출조건,간접 정보확인/탐색이다. 정상 절차와 문맥을 구분해야 한다. threshold9개는 모두0.5다.

실패는 ok=false/result=null/error.code다. INVALID_JSON/INVALID_REQUEST400, INPUT_TOO_LONG422, NOT_READY503, TOKENIZER_CONTRACT/MODEL_INFERENCE_ERROR500. manifest/파일초기화 실패도 호출 backend에서 미준비로 처리해야 하며 위험도0으로 바꾸지 않는다. 이 패키지는 HTTP 서버 자체가 아니다.

## 실제 검증·한계

프로젝트 밖 임시 폴더의 새 CPU 프로세스에서201텐서 일치,부모 대비201텐서 변경,학습/추론 logits차이0.0,반복차이0.0,한국어/history,400/422/503,CLI malformed JSON400·정상200·초과422를 검증했다. 단건과 다른 길이의 배치 사이에는 FP32계산순서에 따른 최대2.384e-7 logit 차이가 있었고 동일 배치 조건에서 비교했다.

합성 잠정 라벨·미검수 상태를 유지한다. 사람2인검수,새 독립 TEST,실통화/STT,backend HTTP/동시성/앱 경고 연결과 운영 배포 승인은 미완료다. MODEL_CARD/DATA_CARD와 동일 VALIDATION 결과를 함께 인계한다. 원본 v1/v2와 기존 TEST·threshold는 변경하지 않았다.
