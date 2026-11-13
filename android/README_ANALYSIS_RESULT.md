# 분석 결과 디테일 화면

Android에서 `분석 종료`를 누르면 결과 디테일 화면이 열리고, 서버의 종료 응답이 도착하면 최종 점수와 종료 일시가 반영된다. **통화 전체의 제목과 요약을 생성하는 기능은 백엔드에서 개발 중이며, Android에는 아직 연결되지 않았다.** 현재 보이는 문구는 기존 분석 응답으로 채운다.

## 현재 제목과 요약에 표시하는 값

| 화면 항목 | 현재 데이터와 표시 방식 | 데이터가 없을 때 |
| --- | --- | --- |
| 상단 제목 | 마지막 분석의 문맥 판단이 성공하면 `context_judgment.result.risk_types`에서 앱이 지원하는 유형을 읽는다. 예를 들어 `institution_impersonation`과 `money_transfer`는 ‘기관 사칭 · 계좌 이체 요구’로 표시한다. | 표시할 유형이 없으면 ‘최종 분석 결과’를 사용한다. |
| 결과 요약 | 마지막 분석의 `context_judgment.result.reason`을 표시한다. 이 문장은 해당 문맥 판단의 근거다. | 분석 결과는 있지만 근거가 없으면 ‘문맥 요약이 제공되지 않았습니다.’를 표시한다. 분석 결과 자체가 없으면 요약 카드를 표시하지 않는다. |

종료 응답에서 마지막 분석은 `last_analysis`에 들어 있다. ‘종합 경고’는 별도 항목이며, 분석 당시 경고를 우선 표시한다. 결과 점수가 없으면 화면에는 0점만 표시하고, 서버가 실제로 0점을 반환하면 ‘0점 · 정상’으로 표시한다.

## 백엔드 개발 후 연결할 부분

1. 백엔드 담당자는 통화 단위 제목과 요약이 어느 응답에 포함되는지, 필드 이름과 타입, 생성 중이거나 생성에 실패했을 때의 값을 앱·서버 계약에 명시한다. 현재 저장소의 종료 응답 계약에는 두 생성 필드가 정의돼 있지 않다. [앱·서버 계약](../server/document/APP_SERVER_CONTRACT.md)
2. Android 담당자는 확정된 필드를 결과 모델에 추가하고 서버 응답에서 읽는다. [RiskAnalysisClient.kt](app/src/main/java/com/example/pic_ai_app/data/stt/RiskAnalysisClient.kt)
3. 결과 디테일 화면에서 서버가 제공한 제목과 요약을 각각 우선 표시한다. 한쪽 값만 오거나 기존 응답처럼 두 값이 모두 없을 때는 해당 항목에 위 표의 표시 방식을 적용한다. [AnalysisResultDetailScreen.kt](app/src/main/java/com/example/pic_ai_app/presentation/screens/AnalysisResultDetailScreen.kt)
