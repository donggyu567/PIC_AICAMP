# atonlee 단독 ONNX 간단 평가

앱·백엔드와 독립적으로 PC CPU에서 이름/주소 탐지를 확인합니다. PyTorch나 GPU는 필요 없습니다.
모델의 최종 정확도는 별도 STT 평가 데이터로 검증해야 합니다.

## 다운로드 후 가장 간단한 사용법

`start.cmd`를 탐색기에서 더블클릭하면 문장을 계속 입력할 수 있습니다.
VS Code PowerShell 터미널에서는 프로젝트 루트에서 아래 한 줄을 실행합니다.

```powershell
.\models\ner\start.cmd
```

모델을 한 번 불러온 뒤 문장을 입력하고 Enter를 누르면 탐지 결과와 이름·주소 마스킹 결과가 표시됩니다.
`/test`는 예제 14개 전체 평가, `/help`는 도움말, `/quit` 또는 Ctrl+C는 종료입니다.
입력과 결과를 파일로 저장하지 않으며, 기본적으로 이미 다운로드된 모델만 사용합니다.
자유 입력은 정답이 없으므로 정확도 점수를 계산하지 않습니다. 한 줄에 한 문장을 입력하세요.

INT8도 다운로드했다면 `.\models\ner\start.cmd --variant int8`로 실행합니다.

## 실행

프로젝트 루트에서 실행합니다. Python 3.11 또는 3.12를 권장합니다.
아래 설치 명령은 가상환경과 패키지 파일을 생성합니다.

```powershell
py -3.12 -m venv models/ner/.venv
models/ner/.venv/Scripts/python.exe -m pip install -r models/ner/requirements.txt
```

모델 다운로드 없이 예제 형식만 검증할 수 있습니다. 이 명령에는 외부 패키지가 필요 없습니다.

```powershell
py -3.12 models/ner/run.py --check-cases
```

첫 추론에는 모델 파일이 필요합니다. **파일 다운로드에 동의하는 경우에만** 아래 명령을 실행합니다.
`--download`는 선택한 ONNX와 tokenizer.json, config.json을 Hugging Face 기본 캐시에 다운로드하도록 허용합니다.
FP32 ONNX 약 56.6MB, INT8 약 14.7MB이며 부속 파일 용량이 추가됩니다. 결과 파일은 생성하지 않습니다.

```powershell
models/ner/.venv/Scripts/python.exe models/ner/run.py --download
models/ner/.venv/Scripts/python.exe models/ner/run.py --variant int8 --download
```

이후 `--download` 없이 실행하면 캐시만 사용합니다. 캐시가 없으면 안내 후 종료합니다.
텍스트는 로컬에서 처리하며 추론 API로 전송하지 않습니다. 원문과 탐지 결과는 콘솔에 출력됩니다.

```powershell
models/ner/.venv/Scripts/python.exe models/ner/run.py --text "제 이름은 윤서진이고 서울시 마포구 월드컵북로 45에 살아요."
```

## 평가 기준과 예제 편집

`cases.jsonl`은 한 줄에 한 사례이며, 수작업으로 만든 14개 동작 점검용 가상 예제입니다.
실제 STT에서 수집한 표본이나 통계적으로 대표성 있는 벤치마크가 아닙니다.
고정된 모델 revision으로 실행하므로 FP32/INT8 비교에서 원본 버전이 바뀌지 않습니다.

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

- https://huggingface.co/atonlee/koelectra-ko-pii-ner
- https://huggingface.co/atonlee/koelectra-ko-pii-ner/tree/1e75c01e707232401883cf364151bbe2e560c708
- https://onnxruntime.ai/docs/api/python/api_summary.html
