# atonlee 단독 ONNX 간단 평가

앱·백엔드와 독립적으로 PC CPU에서 이름·주소 탐지를 확인하는 테스트 도구입니다.
모델은 이미 `models/ner/onnx`에 포함되어 있으므로 별도 다운로드 없이 사용합니다.
처음 사용하는 PC에서는 Python 가상환경을 만들고 필요한 패키지만 설치하면 됩니다. PyTorch나 GPU는 필요 없습니다.

## 폴더 구성

```text
models/ner/
├─ .venv/               # 각 PC에서 생성하는 Python 가상환경
├─ onnx/
│  ├─ model.onnx        # FP32 모델, 약 56.6MB
│  ├─ model_int8.onnx   # INT8 모델, 약 14.7MB
│  ├─ config.json       # 모델 설정 및 라벨 매핑
│  └─ tokenizer.json   # 토크나이저
├─ cases.jsonl          # 정답을 표시한 예제 14개
├─ requirements.txt     # 설치할 패키지 목록
├─ run.py               # 모델 실행 및 평가 코드
└─ start.cmd            # Windows 대화형 실행 파일
```

`run.py`는 자신의 위치를 기준으로 `onnx` 폴더를 찾습니다. Hugging Face 캐시를 사용하지 않습니다.
다른 PC에서도 위 파일 구성을 유지하고, `.venv`는 복사하지 말고 해당 PC에서 새로 생성하세요.

## 1. 가상환경 생성 및 패키지 설치 — 최초 1회

Windows의 VS Code에서 프로젝트를 열고 **PowerShell 터미널**을 사용합니다.
아래 명령은 모두 `models` 폴더가 보이는 **프로젝트 루트(`PIC_AICAMP`)**에서 실행합니다.
`models/ner` 폴더에서 실행하는 명령이 아닙니다.

Python 3.12와 Python Launcher(`py`)가 설치되어 있는지 확인합니다.

```powershell
py -3.12 --version
```

가상환경을 만들고 패키지를 설치합니다. 이 설치 단계에는 패키지를 받을 인터넷 연결이 필요합니다.

```powershell
py -3.12 -m venv .\models\ner\.venv
.\models\ner\.venv\Scripts\python.exe -m pip install -r .\models\ner\requirements.txt
```

가상환경의 Python을 직접 실행하므로 `Activate.ps1`을 실행할 필요는 없습니다.
이미 이 위치에 정상적인 가상환경과 패키지가 준비되어 있다면 바로 다음 단계로 진행합니다.

## 2. 문장을 직접 입력하며 테스트

```powershell
.\models\ner\start.cmd
```

또는 탐색기에서 `models/ner/start.cmd`를 더블클릭합니다.
모델을 한 번 불러온 뒤 문장을 입력하고 Enter를 누르면 탐지 결과·이름과 주소의 마스킹 결과·처리 시간이 표시됩니다.
기본 모델은 FP32입니다.

| 입력 | 동작 |
| --- | --- |
| 일반 문장 | 해당 문장 탐지 및 마스킹 |
| `/test` | `cases.jsonl` 예제 전체 평가 |
| `/help` | 사용법 표시 |
| `/quit` 또는 Ctrl+C | 종료 |

한 줄에 한 문장을 입력하세요. 자유 입력에는 정답이 없으므로 정확도 점수를 계산하지 않습니다.
입력은 로컬에서 처리하고 원문과 결과는 콘솔에만 표시합니다. 추론 API로 전송하거나 결과 파일을 생성하지 않습니다.

INT8 모델로 대화형 테스트를 실행하려면 다음 명령을 사용합니다.

```powershell
.\models\ner\start.cmd --variant int8
```

## 3. 예제 일괄 평가 및 개별 실행

대화형 모드에 들어가지 않고 예제를 평가하려면 아래 명령을 실행합니다.
FP32와 INT8을 같은 예제로 비교할 수 있습니다.

```powershell
# FP32 예제 평가
.\models\ner\.venv\Scripts\python.exe .\models\ner\run.py

# INT8 예제 평가
.\models\ner\.venv\Scripts\python.exe .\models\ner\run.py --variant int8

# 문장 하나만 확인
.\models\ner\.venv\Scripts\python.exe .\models\ner\run.py --text "제 이름은 윤서진이고 서울시 마포구 월드컵북로 45에 살아요."

# 모델을 불러오지 않고 예제 형식과 정답 위치 확인
.\models\ner\.venv\Scripts\python.exe .\models\ner\run.py --check-cases
```

모델 다운로드 옵션은 붙이지 않습니다. 현재 코드에는 과거의 `--download` 옵션과 캐시 관련 오류 안내가 남아 있지만,
실제 모델 로딩은 `models/ner/onnx`의 파일만 읽으며 해당 옵션으로 다운로드하지 않습니다.

## 실행이 안 될 때

- **`py` 또는 Python 3.12를 찾을 수 없음:** Python 3.12와 Python Launcher 설치 여부를 확인한 뒤 터미널을 다시 엽니다.
- **`python.exe` 경로를 찾을 수 없음:** 프로젝트 루트에서 실행 중인지, `models/ner/.venv/Scripts/python.exe`가 있는지 확인합니다. 이전 `models/ner/quickcheck` 경로는 사용하지 않습니다.
- **패키지 import 오류:** 위의 가상환경 Python으로 `pip install -r` 명령을 다시 실행합니다.
- **모델 파일을 찾을 수 없음:** `models/ner/onnx` 안에 선택한 ONNX, `config.json`, `tokenizer.json`이 있는지 확인합니다. 캐시 폴더에만 파일이 있어서는 실행되지 않습니다.

## 평가 기준과 예제 편집

`cases.jsonl`은 한 줄에 한 사례이며, 수작업으로 만든 14개 동작 점검용 가상 예제입니다.
실제 STT에서 수집한 표본이나 통계적으로 대표성 있는 벤치마크가 아닙니다.
사용하는 모델 출처 revision은 아래 출처에 기록되어 있습니다.
실행 코드는 로컬 파일을 읽으며 파일 내용이 해당 revision과 일치하는지 자동 검증하지는 않습니다.
FP32/INT8 비교 시에는 같은 버전에서 가져온 모델과 토크나이저·설정을 사용하세요.

```json
{"id":"my_case", "annotated":"[NAME:윤서진]이고 주소는 [ADDRESS:서울시 마포구 월드컵북로 45]예요."}
```

마킹을 제거한 원문을 모델에 넣고, 마킹 위치를 정답 문자 구간으로 사용합니다.
같은 이름이 여러 번 나오면 각 위치를 각각 표기합니다. 개인정보 없는 문장은 마킹 없이 추가합니다.
NAME과 ADDRESS는 빠짐없이 주석 처리해야 합니다. 그 외 유형은 이 평가 범위에 포함되지 않습니다.
대괄호는 주석 전용이며 원문 대괄호·중첩 주석은 지원하지 않습니다.
다른 파일은 `--cases 경로`로 지정할 수 있습니다. `--text` 모드는 정답이 없으므로 점수를 계산하지 않습니다.

- NAME, ADDRESS별 및 전체 micro Precision/Recall/F1: 유형과 시작·끝 위치가 모두 같아야 정답입니다.
- Fully masked gold entities: 정답 구간의 모든 문자가 NAME/ADDRESS 마스킹 영역에 포함된 비율입니다. 예측 유형은 무시합니다.
- Positive cases with any unmasked gold characters: 정답 개인정보가 일부라도 남는 발화 수입니다.
- Negative cases with a false positive: 이름·주소가 없는 발화를 잘못 가리는 경우입니다.
- 분모가 0인 비율은 N/A입니다. 너무 넓게 가려도 완전 마스킹 비율은 높아지므로 반드시 Precision과 함께 봅니다.
- 지연시간은 토크나이징·CPU 추론·BIO 병합·치환을 포함합니다. 로딩·다운로드·콘솔 출력은 제외하며 첫 warm-up도 제외합니다. Android 성능을 의미하지 않습니다.

모든 예측 유형은 콘솔에 표시하지만 마스킹과 점수 계산은 NAME/ADDRESS만 사용합니다.
NAME은 화면의 마스킹 결과에서 PERSON으로 바꿉니다. 번호류 REGEX/RULE은 포함하지 않습니다.
PLACE는 자동으로 마스킹하지 않습니다. `partial_address` 사례는 우리 정책상 주거 지역도 가려야 한다는 가정으로 ADDRESS를 정답 지정했습니다.
따라서 해당 사례의 실패는 모델 카드의 주소 정의와 프로젝트 정책 차이일 수 있습니다.
최대 512토큰(특수 토큰 포함)을 넘으면 오류로 종료하여 긴 문장을 몰래 잘라 평가하지 않습니다.
BIO에서 독립된 I 태그는 새 개체로 복구합니다. 별도 신뢰도 임계값이나 사전/주소 보정 규칙은 적용하지 않습니다.

실제 정확도 비교에는 별도 STT 발화를 정답 표기하고, 규칙/임계값을 조정하는 데이터와 최종 평가 데이터를 분리하세요.
이 스크립트는 제공된 두 ONNX의 동작 비교이며 PyTorch 원본과의 수치 동등성 검증은 아닙니다.

## 출처

- [atonlee 모델 카드](https://huggingface.co/atonlee/koelectra-ko-pii-ner)
- [사용한 모델 revision](https://huggingface.co/atonlee/koelectra-ko-pii-ner/tree/1e75c01e707232401883cf364151bbe2e560c708)
- [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html)
