# PIC 실제 OpenAI LLM 비교 평가 안내

작성·실행 확인일은 2026-11-19다. 수신 대상은 PIC의 LLM 비교 평가를 진행할 팀원이다.

## 1. 평가 목적과 실행 환경

AWS에 평가용 JSON 파일을 올리고, 기존 서버의 Python 가상환경에서 평가 스크립트를 실행한다. 현재 서버의 프롬프트와 입력·출력 스키마, 보정 문장의 마스킹 토큰 보존 및 근거 발화 번호 검증을 재사용한다.

| 항목 | 현재 기본값 |
|---|---|
| AWS 환경 | Lightsail 서울, Ubuntu, 4GB RAM, 2 vCPU |
| 서버 SSH 주소 | ubuntu@3.34.203.209 |
| 서버 프로젝트 | /home/ubuntu/PIC_AICAMP |
| Python | /home/ubuntu/PIC_AICAMP/.venv/bin/python |
| OpenAI 모델 | 서버의 PIC_CONTEXT_MODEL. 확인한 값은 gpt-5.6-luna |
| 처리 등급 | fast 요청. 이번 응답에서는 priority 반환 |
| 추론 강도 | low |
| 응답 | JSON 스키마 기반 구조화 출력 |
| 제한 | 출력 최대 2048토큰, 클라이언트 timeout 10초, 자동 재시도 0회 |
| API 옵션 | store=False, truncation=disabled |

이 도구는 보정·문맥 판단 LLM 한 단계의 입력과 응답을 평가한다. 모델의 응답, SDK·통신을 포함한 API 대기 시간, 서버의 응답 검증까지의 시간을 기록한다. 마이크·ElevenLabs STT·기기 마스킹 실행·KoELECTRA 추론·누적 점수·앱 화면 지연은 별도 통합 평가 항목이다.

서버의 환경 설정에서 OpenAI API 키를 읽는다. 실행하려면 관리자에게 승인받은 SSH 계정·키가 필요하다. 접속 권한이 없는 팀원은 평가 JSON과 비교 조건을 담당자에게 전달하고 결과 JSONL을 받아 분석할 수 있다.

## 2. 전달 파일과 Git 반영 범위

| 저장소 기준 경로 | 역할 |
|---|---|
| server/evaluate_llm.py | 독립 실행 평가 도구 |
| server/document/llm_evaluation_cases.json | 정상·피싱·예방교육 가상 샘플 3건 |
| server/document/LLM_EVALUATION_GUIDE.md | 이 안내서 |
| server/README.md | 평가 안내 링크와 검증 기록 |

공유 브랜치는 codex/llm-evaluation이다. 해당 브랜치에서 위 파일을 받으면 같은 평가 절차를 재현할 수 있다. 실제 운영 API 수정이나 서비스 재시작은 이 평가 도구 실행에 필요하지 않다.

환경 설정 파일 .env, API 키, SSH 개인키 및 평가 결과는 Git에 추가하지 않는다. 결과는 /home/ubuntu/pic-llm-evaluation 아래에 저장한다. 서버에서 사용하는 기존 키를 개인 PC로 복사할 필요는 없다.

저장소 루트에서 사용할 파일 선택 명령은 다음과 같다. server/README.md에는 기존 모델 로딩 측정 기록도 포함돼 있으므로 커밋 전 diff를 함께 확인한다.

~~~powershell
git add server/evaluate_llm.py
git add server/document/llm_evaluation_cases.json
git add server/document/LLM_EVALUATION_GUIDE.md
git add server/README.md
git diff --cached --stat
~~~

## 3. 입력 파일 작성

입력은 UTF-8 JSON 배열이다. 한 항목이 한 시점의 대화 문맥이며, API 호출 한 번에 대응한다.

~~~json
[
  {
    "case_id": "phishing-001",
    "expected_assessment": "suspicious",
    "context": {
      "conversation_id": "eval-phishing-001",
      "current_utterance_id": 2,
      "utterances": [
        {
          "utterance_id": 1,
          "text": "검찰청 수사관입니다. 당신 명의의 계좌가 범죄에 이용됐습니다."
        },
        {
          "utterance_id": 2,
          "text": "안전 계좌 [ACCOUNT_NUMBER]로 지금 돈을 보내세요."
        }
      ]
    }
  }
]
~~~

- case_id는 평가 사례를 구분하는 중복 없는 이름이다.
- conversation_id는 파일 안에서 문맥을 구분하는 값이다. 이 도구는 HTTP 통화 API를 거치지 않으므로 평가용 ID를 사용할 수 있다.
- utterance_id는 1부터 순서대로 작성한다.
- current_utterance_id는 마지막 발화 번호다. 마지막 발화만 corrected_text의 보정 대상이며, 이전 발화는 판단 문맥이다.
- 실제 앱에서는 이전 발화에 저장된 보정 문장을 사용한다. 정적 비교에서는 두 모델에 동일한 이전 문맥을 제공하고, 각 모델의 이전 보정 결과를 다시 넣는 연속 평가와 구분한다.
- 개인정보는 사전에 마스킹하거나 가상의 값으로 준비한다. 이 평가 도구는 NER 마스킹을 실행하지 않는다.
- expected_assessment는 선택 항목이다. suspicious, no_clear_risk, insufficient_context 중 하나를 적거나 생략한다.
- 의심 판단의 근거, 위험 유형 및 보정 품질은 출력과 정답 자료를 별도로 대조한다.

동봉한 3건은 실행 확인용 가상 예시이며 검수된 평가 데이터셋이 아니다. expected_assessment도 비교 형식을 설명하는 예시 라벨이다. 정식 평가에는 별도 정답 기준과 검수, 모델 학습 데이터와의 분리 조건을 기록한다.

## 4. Windows에서 AWS로 업로드

먼저 평가 도구와 샘플 파일을 받은 프로젝트의 최상위 폴더에서 실행한다. 아래 Project와 Key에는 각자 실제 경로를 입력한다.

~~~powershell
$Project = 'C:/path/to/PIC_AICAMP'
$Key = 'C:/path/to/your-approved-ssh-key.pem'
$Server = 'ubuntu@3.34.203.209'

Set-Location -LiteralPath $Project

scp -i $Key ./server/evaluate_llm.py "${Server}:/home/ubuntu/PIC_AICAMP/server/evaluate_llm.py"
scp -i $Key ./server/document/llm_evaluation_cases.json "${Server}:/home/ubuntu/PIC_AICAMP/server/document/llm_evaluation_cases.json"

ssh -i $Key $Server
~~~

추가로 만든 평가 파일은 기존 샘플을 덮어쓰기보다 별도 이름으로 올리면 이력을 유지하기 편하다.

~~~powershell
scp -i $Key ./team_cases.json "${Server}:/home/ubuntu/team_cases.json"
~~~

2026-11-19 실행 확인 시점에는 평가 스크립트와 샘플을 위 서버 경로에 업로드했다. 새 로컬 변경으로 평가하려면 해당 파일을 다시 업로드한다. 기존 서버 전체를 git pull하거나 재시작하는 절차는 포함되지 않는다.

## 5. 서버에서 입력 검사와 실제 실행

다음 명령은 SSH 접속 후 Ubuntu Bash에서 실행한다.

### 5.1 입력 형식만 검사

~~~bash
cd /home/ubuntu/PIC_AICAMP

.venv/bin/python -B -m server.evaluate_llm \
  --input server/document/llm_evaluation_cases.json \
  --validate-only
~~~

이 검사는 API를 호출하지 않는다. JSON 구조, 현재 발화의 마스킹 토큰 형식, 발화 번호를 검사한다. 개인정보가 완전히 제거됐는지를 판정하는 검사는 아니다.

### 5.2 현재 모델 평가

~~~bash
umask 077
mkdir -p /home/ubuntu/pic-llm-evaluation
RUN_DIR=$(mktemp -d /home/ubuntu/pic-llm-evaluation/run.XXXXXX)
echo "$RUN_DIR"

.venv/bin/python -B -m server.evaluate_llm \
  --input server/document/llm_evaluation_cases.json \
  --output "$RUN_DIR/baseline.jsonl" \
  --repeat 3
~~~

샘플 3건을 3회 반복하므로 실제 API 호출은 9회이며 API 사용료가 발생한다. 모든 입력·응답이 유효해도 판단 내용은 회차별로 달라질 수 있다.

추가 평가 파일은 --input /home/ubuntu/team_cases.json으로 지정한다.

출력 파일은 새 이름으로 만든다. 기존 파일명으로 실행하면 덮어쓰기 없이 중단한다. 각 응답이 끝날 때 결과를 저장하므로 실행이 중단돼도 완료된 사례를 읽을 수 있다. 재실행은 자동 이어받기가 아니므로 남은 사례를 구분해 새 출력 파일에 실행한다.

### 5.3 비교 모델 평가

OpenAI Responses API, 구조화 출력, 지정한 추론 강도·처리 등급을 지원하고 해당 프로젝트에서 사용할 수 있는 모델 ID를 입력한다.

~~~bash
.venv/bin/python -B -m server.evaluate_llm \
  --input server/document/llm_evaluation_cases.json \
  --output "$RUN_DIR/comparison.jsonl" \
  --model 'MODEL_ID' \
  --effort low \
  --service-tier fast \
  --repeat 3
~~~

MODEL_ID를 실제 모델 ID로 바꾼다. 현재 기본 모델을 Standard와 비교하려면 --service-tier default를 사용한다. 비교 목적에 맞춰 입력·프롬프트·추론 강도·처리 등급을 고정하거나, 바꾼 조건을 표에 남긴다.

이 명령의 모델·설정 변경은 해당 평가 호출에 적용된다. 평가 파일에는 요청한 설정과 응답이 반환한 모델·처리 등급을 모두 기록한다.

## 6. 결과에서 확인할 항목

출력은 한 줄에 JSON 객체 한 개가 있는 JSONL이다.

| 필드 | 의미 |
|---|---|
| case_id, repeat | 평가 사례와 반복 회차 |
| started_at_utc | 호출 시작 시각 |
| requested_model, returned_model | 요청 모델과 실제 반환 모델 |
| requested_service_tier, returned_service_tier | 요청·반환 처리 등급 |
| reasoning_effort | 요청한 추론 강도 |
| prompt_sha256 | 사용한 프롬프트 내용의 해시 |
| input | 평가에 사용한 문맥 |
| api_seconds | API 요청 직전부터 SDK 응답 수신까지 |
| total_seconds | API 호출 및 응답 검증을 마칠 때까지 |
| usage | 입력·출력·캐시·추론 토큰 등 API가 반환한 사용량 |
| raw_output | 실제 반환된 출력 텍스트 |
| result | 검증을 통과한 corrected_text와 context_judgment |
| status, error_type | 호출·응답 검증 성공 여부와 실패 유형 |
| expected_assessment, assessment_match | 선택한 예시 정답과 판단 분류의 일치 여부 |
| request_id | API가 반환한 요청 추적 ID |

status=ok는 API 호출과 형식·토큰·근거 참조 검증이 통과했다는 의미다. 정답 분류와의 일치 여부는 assessment_match로 따로 확인한다. API가 응답한 뒤 검증이 실패해도 받은 usage와 출력은 기록한다. SDK 요청 자체가 실패한 경우 사용량을 받지 못할 수 있으며, usage가 없다고 미과금을 단정하지 않는다.

스크립트가 실패 건수 때문에 종료 코드 1을 반환해도 저장된 결과를 먼저 확인한다. 자동 재호출은 하지 않는다.

## 7. 결과를 Windows로 받기

서버에서 출력한 RUN_DIR의 실제 경로를 확인한다. Windows PowerShell에서 서버 경로를 정확히 입력해 받는다.

~~~powershell
scp -i $Key "${Server}:/home/ubuntu/pic-llm-evaluation/run.XXXXXX/baseline.jsonl" ./baseline.jsonl
scp -i $Key "${Server}:/home/ubuntu/pic-llm-evaluation/run.XXXXXX/comparison.jsonl" ./comparison.jsonl
~~~

run.XXXXXX는 실제 생성된 폴더명으로 바꾼다.

## 8. 비교 평가를 정리하는 방법

| 영역 | 확인할 항목 |
|---|---|
| 보정 | 부정·인용·예방교육 의미 보존, 불필요한 의미 추가·변경 |
| 마스킹 | 토큰의 종류·개수·순서 보존 |
| 문맥 | suspicious / no_clear_risk / insufficient_context의 정답 일치 |
| 근거 | 실제로 위험한 발화를 선택했는지, 이유가 입력을 벗어나지 않는지 |
| 위험 유형 | 8개 위험 유형의 정답과 예측 비교 |
| 오류 | 거부·타임아웃·미완료·검증 실패 수와 전체 시도 수 |
| 지연 | 평균·중앙값·상위 95%와 표본 수. 실패 사례도 별도 집계 |
| 비용 | usage의 입력·출력·캐시 읽기·캐시 기록 토큰과 실행일 단가 |
| 재현 조건 | 코드 커밋, 프롬프트 해시, 모델, 설정, 데이터 버전, 실행 시각 |

일치율이나 F1은 별도 평가 코드·정답표로 계산한다. 이 도구는 원본 결과를 수집하며 F1이나 비용을 자동 산출하지 않는다. 캐시·호출 순서와 서비스 상태가 지연 및 비용에 영향을 주므로 비교 모델의 실행 순서·반복 수를 함께 기록한다.

통화의 각 시점을 평가하려면 사례별로 처음부터 현재 시점까지의 prefix를 준비한다. 예를 들어 같은 통화를 1발화까지, 2발화까지, 3발화까지 각각 평가 항목으로 만든다. 각 항목은 독립 호출이다.

## 9. 이번 실제 실행 확인 결과

2026-11-19 AWS에서 기본 설정으로 가상 사례 3건을 각 1회 호출했다. 세 건 모두 응답 검증을 통과했다.

| 사례 | 판단 | API 대기 시간 | 입력 토큰 | 출력 토큰 | 추론 토큰 |
|---|---|---:|---:|---:|---:|
| 정상 대화 | no_clear_risk | 4.5819초 | 914 | 99 | 0 |
| 기관 사칭·송금 요구 | suspicious | 2.4510초 | 935 | 183 | 46 |
| 예방교육 | no_clear_risk | 2.0742초 | 922 | 117 | 0 |

요청 모델과 반환 모델은 gpt-5.6-luna였고 반환 등급은 priority였다. 각 건의 캐시 읽기·기록 토큰은 0이었다. 추론 토큰은 출력 토큰의 구성 항목이므로 비용 계산 때 출력 토큰에 다시 더하지 않는다.

서버 결과 경로는 /home/ubuntu/pic-llm-evaluation/smoke-20261119.lZeRnp/results.jsonl이다. 입력 검사와 미완료 응답의 실패·사용량 보존도 확인했다. 실행 후 운영 서비스와 공개 HTTPS 응답이 정상인 것을 확인했다.

이 3건은 실행 가능 여부를 확인한 표본이다. 정식 품질 평가 결과와 비교하려면 별도 데이터·정답·표본 수를 준비한다. 앞서 측정한 KoELECTRA 모델 로딩 평균 2.53초는 자체 AI 준비 시간이며 LLM 지연과 구분한다.

## 10. 기존 코드와 평가 도구의 관계

- 서버 프롬프트와 클라이언트 설정을 server.analysis.context_service에서 가져온다.
- 입력·출력 타입 및 검증은 server.analysis.context_contracts에서 가져온다.
- 현재 입력의 마스킹 계약 검증은 models.llm_correction.MaskedTranscript를 사용한다.
- 별도 평가 루프에서 동일한 Responses API 설정으로 호출하고 시간·사용량·응답을 수집한다.
- 평가 파일의 conversation_id는 HTTP 통화 저장소에 등록하거나 기록을 저장하는 용도로 사용하지 않는다.
- 통화 종료 요약·피해 경위 초안 생성 품질은 각각 별도 프롬프트와 출력 형식을 대상으로 추가 평가해야 한다.
