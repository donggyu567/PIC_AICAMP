# 쉼픽 Analysis Result v0.1

> 상태: **Draft / MVP v0.1**
> 이 문서는 Analysis 결과 계약을 설명하며, Backend API 계약은 정의하지 않습니다.

## 1. 목적

신규 쉼터 배치 전후의 Grid별 접근성과 배치 반영 위험도를 비교하기 위한 MVP Analysis Result 계약입니다.

샘플 결과는 [`data/sample/placement_risk_result_v0_1.json`](data/sample/placement_risk_result_v0_1.json)에서 확인할 수 있습니다. 이 파일은 production 실데이터가 아닌 합성 검증 시나리오이며, `simulate_placement_risk()`의 실제 반환값을 직렬화한 결과입니다.

## 2. 공식 취약도

`vulnerability_score`는 지역의 구조적 취약도를 나타내며 신규 쉼터 배치로 변경되지 않습니다. 공식 구성 요소는 다음과 같습니다.

- `heat_score`
- `elderly_score`
- `farmland_score`

기존 공식 `risk_level`도 `vulnerability_score`에 따른 구조적 위험 등급이므로 Before와 After에서 동일합니다.

## 3. Placement Risk

`placement_risk_score`는 접근성을 포함하는 별도의 MVP 배치 반영 위험도입니다.

```text
heat_score × 0.25
+ elderly_score × 0.25
+ farmland_score × 0.25
+ coverage_gap_score × 0.25
```

## 4. Placement Risk Level

| 점수 범위 | `placement_risk_level` |
|---|---|
| `0 <= score < 25` | `LOW` |
| `25 <= score < 50` | `MODERATE` |
| `50 <= score < 75` | `HIGH` |
| `75 <= score` | `VERY_HIGH` |

`placement_risk_level`은 접근성을 포함하는 배치 반영 위험 등급입니다. 구조적 취약도를 나타내는 기존 공식 `risk_level`과 의미가 다른 별도 필드입니다.

## 5. 공간 기준

- 분석 CRS: `EPSG:5179`
- 쉼터 접근권: `300m` 이하(정확히 300m 포함)
- API/Frontend 좌표 표현: `EPSG:4326`, `[longitude, latitude]`

Analysis Result v0.1 자체에는 배치 좌표가 포함되지 않으며, 위 좌표 규칙은 향후 요청 또는 지도 데이터에서 좌표를 전달할 때 적용합니다.

## 6. Blind Spot

`blind_spot`은 다음 조건으로 판정합니다.

```text
current_covered == false
AND risk_level in {HIGH, VERY_HIGH}
```

판정에는 공식 구조적 `risk_level`을 사용하며 `placement_risk_level`을 사용하지 않습니다.

## 7. Grid Result Schema

`simulate_placement_risk()`의 실제 반환 구조는 다음과 같습니다. `number | null`, `boolean | null`은 분석 불충분 상태에서 `null`이 될 수 있음을 뜻합니다.

### PlacementRiskGridState

| 필드 | 타입 | 의미 |
|---|---|---|
| `nearest_shelter_distance_m` | `number \| null` | 가장 가까운 쉼터까지의 거리(m) |
| `shelter_count` | `integer \| null` | 300m 접근권 안의 쉼터 수 |
| `current_covered` | `boolean \| null` | 300m 접근권 포함 여부 |
| `blind_spot` | `boolean \| null` | 공식 구조적 위험도 기반 사각지대 여부 |
| `vulnerability_score` | `number \| null` | 공식 구조적 취약도 점수 |
| `risk_level` | `string \| null` | 공식 구조적 위험 등급 |
| `placement_risk_score` | `number \| null` | 배치 반영 위험도 점수 |
| `placement_risk_level` | `string \| null` | 배치 반영 위험도 등급 |

### GridPlacementRiskResult

| 필드 | 타입 | 의미 |
|---|---|---|
| `grid_id` | `string` | Grid 식별자 |
| `before` | `PlacementRiskGridState` | 배치 전 상태 |
| `after` | `PlacementRiskGridState` | 배치 후 상태 |
| `newly_covered` | `boolean` | 신규 보호 여부 |

### 전체 Analysis Result

| 필드 | 타입 | 의미 |
|---|---|---|
| `requested_shelter_count` | `integer` | 요청된 신규 배치 수 |
| `selected_placement_ids` | `string[]` | 검증 완료된 배치 ID 목록 |
| `newly_covered_grid_ids` | `string[]` | 신규 보호 Grid ID 목록 |
| `newly_covered_elderly_population` | `integer` | 신규 보호된 취약 Grid의 고령인구 합계 |
| `reduced_blind_spot_count` | `integer` | 감소한 사각지대 Grid 수 |
| `coverage_ratio_change` | `number \| null` | 취약인구 커버리지 비율 변화량 |
| `coverage_comparison` | `CoverageComparison` | 배치 전후 취약인구·사각지대 집계 |
| `grid_results` | `GridPlacementRiskResult[]` | Grid별 배치 전후 결과 |

`coverage_comparison`은 다음 구조입니다.

```json
{
  "total_vulnerable_population": 30,
  "before": {
    "covered_vulnerable_population": 10,
    "vulnerable_population_coverage_rate": 0.3333333333333333,
    "blind_spot_grid_count": 1,
    "blind_spot_area_m2": 250000
  },
  "after": {
    "covered_vulnerable_population": 30,
    "vulnerable_population_coverage_rate": 1.0,
    "blind_spot_grid_count": 0,
    "blind_spot_area_m2": 0
  },
  "improvement": {
    "newly_covered_vulnerable_population": 20,
    "vulnerable_population_coverage_rate_delta": 0.666666666667,
    "blind_spot_grid_reduction_count": 1
  }
}
```

## 8. Before/After 불변/가변 필드

불변 필드:

- `vulnerability_score`
- `risk_level`
- heat, elderly, farmland 등 구조적 입력 데이터

가변 필드:

- `nearest_shelter_distance_m`
- `shelter_count`
- `current_covered`
- `blind_spot`
- `placement_risk_score`
- `placement_risk_level`

구조적 입력 데이터와 각 구성 점수는 계산 입력으로 사용되지만 현재 Grid Result에는 직접 포함되지 않습니다.

## 9. newly_covered

`newly_covered`는 다음 조건일 때만 `true`입니다.

```text
before.current_covered == false
AND after.current_covered == true
```

## 10. Normalization

배치 전 Grid cohort에서 적합한 normalization reference를 배치 후 `coverage_gap_score` 계산에도 동일하게 사용합니다. 따라서 Before/After 점수를 서로 다른 분포로 재정규화하지 않습니다.

## 11. Frontend 시각화 의미

- Before 지도 fill: `before.placement_risk_level`
- After 지도 fill: `after.placement_risk_level`
- 신규 보호 border/highlight: `newly_covered`

즉 fill color는 배치 반영 위험도, border/highlight는 신규 보호 여부를 뜻합니다. 공식 `vulnerability_score`와 `risk_level`은 tooltip 또는 상세 지표로 별도 제공할 수 있습니다. Frontend는 위험도나 신규 보호 여부를 다시 계산하지 않고 Analysis Result를 표시합니다.

현재 결과는 `Mock JSON → placementSimulationService → ComparisonPage → ComparisonMap` 흐름의 원천 데이터로 사용할 수 있습니다. 필드 변환이 필요하면 향후 Front adapter가 담당하며 Analysis 필드명은 변경하지 않습니다.

## 12. Analysis Schema와 API Schema

확정된 범위는 이 문서의 **Analysis Result v0.1 구조**입니다.

다음 API 사항은 아직 TBD입니다.

- Backend endpoint
- HTTP Method
- 요청 envelope
- 응답 envelope
- sync/async 방식
- `job_id`/`status`
- DB 저장 방식
- 분석 데이터 version
- 실데이터 기준시점

## 13. 실행환경과 재현

- 공식 검증 환경: Python `3.11.9` x64
- 사용 문법의 최소 기준: Python `3.10+`
- 의존성 설치: `python -m pip install -r requirements-ai-gis.txt`
- 샘플 재생성: `python -m integration.generate_placement_risk_sample`

Python 3.11.9는 현재 공식 **검증 환경**이며, 프로젝트 공식 최소 버전을 3.11.9로 선언하는 것은 아닙니다.

## 14. v0.1 상태와 알려진 검증 환경 이슈

이 계약은 **Draft / MVP v0.1**입니다. 실데이터 API 및 전체 합천군 데이터 연동 이후 schema와 calibration은 변경될 수 있으므로 production 최종 계약이 아닙니다.

현재 전체 테스트 suite 결과는 `126 passed, 1 failed`입니다. 단일 실패는 `data/raw/boundary/hapcheon_legal_emd_boundary_raw_crs.zip` 원천 fixture가 로컬 저장소에 없어서 발생하는 기존 테스트 환경 문제이며 Placement Risk 기능과 무관합니다. 이 문서화 단계에서는 fixture를 생성하거나 대체하지 않습니다.
