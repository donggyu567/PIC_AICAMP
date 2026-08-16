# Voice-phishing label guide v3.1

## 판단 단위

- `is_phishing`은 현재 발화, speaker, 앞뒤 문맥, source, conversation 전체 흐름을 함께 보고 판단한다.
- `labels`는 현재 발화가 직접 표현하거나 수행하는 위험행위만 기록한다. 앞 발화의 라벨을 자동 상속하지 않는다.
- `is_phishing=false`이면 `labels=[]`로 둔다.
- `is_phishing=true`이면 원칙적으로 하나 이상의 라벨을 부여하지만, 현재 여섯 라벨에 직접 해당하지 않으면 억지로 붙이지 않고 `labels=[]`로 둔 뒤 review queue에 기록한다.
- 피해자가 사기범의 말을 되묻거나 반복하는 발화는 원칙적으로 `is_phishing=false`, `labels=[]`로 둔다.
- 정상 상담에서는 위험 키워드가 등장하거나 적법한 본인확인 절차가 있더라도 전체 문맥과 source가 정상이면 `is_phishing=false`, `labels=[]`로 둔다.

## 허용 라벨

### `institution_impersonation`

공공기관, 금융기관, 기업 또는 조직이나 그 직원·구성원을 사칭하는 현재 발화에 사용한다. 검찰, 경찰, 금융감독원, 은행, 카드사, 기업 고객센터 및 조직 직원 사칭이 포함된다.

기관의 단순 언급만으로는 부여하지 않는다. 세무사, 변호사, 회계사 등 개별 전문직 사칭은 현재 확정 대상이 아니며 피싱 문맥이면 review queue에 기록한다.

### `money_transfer`

송금, 이체, 입금, 현금 전달 등 금전 이전을 직접 요구하거나 유도하는 현재 발화에 사용한다.

### `personal_information`

성명, 생년월일, 전화번호, 주소, 주민등록번호, 계좌정보, 카드정보, 비밀번호, OTP 또는 인증번호를 요구·수집·확인하도록 유도하는 현재 발화에 사용한다.

사건번호, 접수번호, 민원번호 및 기타 업무·사건 식별번호는 현재 확정 대상이 아니다. 피싱 문맥에서 이를 요구하면 `labels=[]`로 두고 review queue에 기록한다.

### `app_installation`

앱 또는 APK 설치, 원격제어 프로그램 설치, 원격제어 프로그램 실행을 유도하는 현재 발화에 사용한다.

단순 URL 입력, 링크 클릭, 웹사이트 접속·검색, 검색어 입력, 웹페이지 탐색에는 사용하지 않는다. 이러한 행위가 피싱 문맥의 일부이면 `is_phishing=true`, `labels=[]`로 둘 수 있으며 review queue에 기록한다.

### `secrecy`

가족, 지인, 금융기관, 수사기관 등 제삼자에게 알리지 말라고 직접 요구하는 비밀 유지 발화에 사용한다. 단순히 전화를 끊지 말거나 기다리라고 하는 통화 유지 요청만으로는 사용하지 않는다.

### `threat_pressure`

체포, 계좌 동결, 처벌, 금전 손실, 명시적 시간제한 등 불이익을 이용해 행동을 강요하는 현재 발화에 사용한다. `지금`, `바로`, `즉시` 같은 표현만으로는 사용하지 않는다.

## Review queue

- 모든 `is_phishing=true` 및 `labels=[]` 발화를 포함한다.
- 정상 데이터라도 source가 없으면 피싱과 혼동하기 쉬운 개인정보 요청, 기관·기업 직원 표현 등 hard-negative 발화를 포함할 수 있다.
- 정상 hard-negative 항목은 `provisional_is_phishing=false`, `provisional_labels=[]`를 유지한다.
- 각 항목에 구체적인 `reason`과 `status="needs_review"`를 기록한다.
