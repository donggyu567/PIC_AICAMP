# Rule · Resolver 초기 정책

## Rule

- 모든 후보의 위치는 입력 원문 기준의 `[start, endExclusive)`를 유지한다.
- 원문 밖을 가리키는 후보는 개인정보 값이 포함되지 않은 예외 메시지와 함께 실패시킨다.
- 형식과 문맥이 충분하면 후보를 유지하고, 명확한 오탐 문맥이면 제거한다.
- 카드/계좌처럼 다른 유형임이 문맥상 분명하면 유형을 바꾸고 `source = RULE`, `confidence = null`로 반환한다.
- 단순 검증을 통과한 후보는 기존 출처와 신뢰도를 유지한다.
- 생년월일은 같은 문장과 후보 주변 36자 안의 생년월일 문맥을 사용한다. 회의·예약·행사 등 일정 문맥은 오탐으로 제거한다.
- 형식이 일부 깨졌더라도 주민번호·전화번호·생년월일 문맥이 명시적이면 STT 오류 가능성을 고려해 보수적으로 유지한다.
- 이메일은 후보 원문을 변형하지 않고 전체 문자열의 형식과 경계를 검증한다. STT로 `@`, `.`이 발음형으로 깨진 후보는 가까운 이메일 문맥이 명시적일 때만 보수적으로 유지한다.
- 비밀번호는 `비밀번호`, `비번`, `패스워드`, `password`, `PIN 번호`와 값이 같은 발화에 명시적으로 연결된 경우에만 직접 생성한다. 단순 언급·변경·분실 문장은 생성하지 않는다.

## Resolver

- 동일 범위·동일 유형은 한 건으로 정리한다. 동일 출처끼리만 confidence를 비교한다.
- 유형 우선순위는 `PW > RRN > CARD_NUMBER > ACCOUNT_NUMBER > PHONE_NUMBER > EMAIL > BIRTH > ADDRESS > PERSON`이다.
- 우선순위는 개인정보 의미가 더 구체적인 유형을 겹친 구간에 선택하기 위한 것이며, `RULE` 출처 자체를 모든 유형에서 우선하지 않는다.
- `PW`는 명시적 비밀번호 문맥에서 생성되므로 겹친 구간에서 가장 먼저 선택한다.
- 부분 겹침이나 포함 관계는 구간 경계에서 분할한다. 우선순위가 높은 후보는 겹친 부분을 담당하고, 낮은 후보가 단독으로 덮던 앞뒤 구간은 유지한다. 따라서 입력 후보가 덮은 개인정보 구간이 Resolver 처리로 노출되지 않는다.
- 인접한 `[0, 3)`, `[3, 8)` 후보는 겹침이 아니므로 합치지 않는다.
- 반환값은 시작 위치 오름차순이며 중복과 겹침이 없다.

이 정책은 Regex와 NER의 실제 출력 사례가 모이면 대표 충돌 테스트를 추가하면서 조정한다.

## 핵심 함수 정리

### `DefaultNumberMaskingRuleEngine.validate()`

Regex가 생성한 개인정보 후보를 원문 문맥과 유형별 규칙으로 검증한다. 검증된 후보와 원문에서 직접 찾은 PW 후보를 합쳐 반환한다.

- 입력: `String` 형식의 STT 원문, `List<MaskCandidate>` 형식의 Regex 후보 목록
- 출력: 유지·제거·재분류가 끝난 `List<MaskCandidate>`
- 실패: 후보 위치가 원문 범위를 벗어나거나 지원 대상이 아닌 유형이면 예외 전달

### 유형별 `validate()`

`PhoneNumberRule`, `ResidentNumberRule`, `CardNumberRule`, `AccountNumberRule`, `BirthRule`, `EmailRule`에서 각 후보의 형식과 가까운 문맥을 확인한다.

- 입력: `String` 형식의 STT 원문, 검증할 `MaskCandidate` 한 건
- 출력: 유지·재분류된 `MaskCandidate` 한 건 또는 명확한 오탐일 때 `null`

### `PasswordRule.detect()`

원문에서 비밀번호 문맥과 연결된 실제 값의 위치를 찾아 PW 후보를 생성한다. 값이 없는 단순 언급은 제외한다.

- 입력: `String` 형식의 STT 원문
- 출력: `List<MaskCandidate>` 형식의 PW 후보 목록

### `DefaultCandidateConflictResolver.resolve()`

NER 후보와 Rule 검증 결과의 완전 중복, 포함 관계, 부분 겹침을 정리한다. 겹치지 않는 최종 후보를 원문 위치순으로 반환한다.

- 입력: `List<MaskCandidate>` 형식의 전체 후보 목록
- 출력: 중복·겹침이 제거된 `List<MaskCandidate>`
- 대상 없음: `emptyList()` 반환

## 전체 파이프라인

1. `NerCandidateDetector.detect(text)`가 이름과 주소 후보를 생성한다.
2. `RegexCandidateDetector.detect(text)`가 번호·생년월일·이메일 후보를 생성한다.
3. `NumberMaskingRuleEngine.validate(text, regexCandidates)`가 Regex 후보를 검증하고 PW 후보를 추가한다.
4. NER 후보와 Rule 결과를 하나의 목록으로 합친다.
5. `CandidateConflictResolver.resolve(candidates)`가 중복과 겹침을 정리한다.
6. `MaskedTextRenderer.render(text, candidates)`가 최종 후보 위치를 실제 마스킹 토큰으로 치환한다.

Rule과 Resolver는 원문을 직접 변경하지 않는다. 실제 문자열 치환은 Renderer에서만 수행한다.

## 연결 방법

추가 설정이나 모델 로딩 없이 기본 구현체를 생성해 `MaskingPipeline`에 전달한다.

```kotlin
val ruleEngine: NumberMaskingRuleEngine = DefaultNumberMaskingRuleEngine()
val conflictResolver: CandidateConflictResolver = DefaultCandidateConflictResolver()
```

Regex 담당자는 다음 조건으로 후보를 전달한다.

- 후보 유형: `PHONE_NUMBER`, `RRN`, `CARD_NUMBER`, `ACCOUNT_NUMBER`, `BIRTH`, `EMAIL`
- 위치: 정규화한 문자열이 아닌 원본 STT 문자열 기준의 `[start, endExclusive)`
- 출처: `MaskSource.REGEX`
- 공백과 하이픈을 제거해 검증하더라도 후보 위치는 구분자가 포함된 원문 범위를 유지

새로운 후보 유형이나 현재 우선순위로 의미를 결정하기 어려운 충돌은 임의로 처리하지 않고, 정책 합의와 대표 테스트를 먼저 추가한다.

## 검증 결과

- Rule 테스트: 유형별 유지·제거·재분류, PW 탐지, 잘못된 원문 범위 검증
- Resolver 테스트: 완전 중복, 같은 범위의 다른 유형, 포함·부분 겹침, 인접 후보, 입력 순서 독립성 검증
- 결과: 총 25개 단위 테스트 통과
