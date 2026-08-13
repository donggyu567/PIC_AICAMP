# ☀️🌿 쉼픽 (쉼터 + Pick)
### 농촌 폭염 대응 자원 최적배치 AI 서비스 
> 농촌지역의 폭염 취약성과 기존 쉼터 현황을 분석해 **폭염 대응 사각지대를 발견**하고,  
> 신규 쉼터의 **우선 배치와 효과 분석을 지원하는 지자체 대상 B2G 의사결정 지원 서비스**

[![Notion](https://img.shields.io/badge/Notion-프로젝트_문서-000000?style=for-the-badge&logo=notion&logoColor=white)](https://app.notion.com/p/EST-20-3b8b9b1146b78075aba1e6d4f13958fd?source=copy_link)

<br>

## 💡 프로젝트 소개

농촌지역의 **폭염·고령인구·농경지·기존 쉼터 데이터**를 결합하여  
기존 폭염 대응시설의 보호가 충분히 닿지 않는 **사각지대**를 발견합니다.

한정된 쉼터의 **우선 배치지역과 판단 근거를 제공하고, 배치 전·후 효과를 비교**하여  
지자체 담당자의 의사결정을 지원합니다.

<br>

## ✨ 주요 기능

- 🗺️ **폭염 취약지역 분석** — 지역별 폭염 취약도 및 사각지대 시각화
- 📍 **쉼터 배치 추천** — 한정된 쉼터 수를 고려한 우선 배치지역 추천
- 📊 **배치 효과 비교** — 기존 / AI 추천 / 사용자 배치안의 커버리지 비교
- 🤖 **AI 설명** — 취약 원인, 추천 근거 및 배치 효과 요약

<br>

## 🔄 Service Flow

`지역 선택` → `취약지역·사각지대 탐색` → `AI 배치안 추천` → `배치 전 · 후 효과 비교` → `최종 검토`

<br>

## 🛠 Tech Stack

### Frontend

![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Leaflet](https://img.shields.io/badge/Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white)

### Backend

![Java](https://img.shields.io/badge/Java-007396?style=for-the-badge&logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-6DB33F?style=for-the-badge&logo=springboot&logoColor=white)

### Data & GIS

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![GeoPandas](https://img.shields.io/badge/GeoPandas-139C5A?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![PostGIS](https://img.shields.io/badge/PostGIS-336791?style=for-the-badge&logo=postgresql&logoColor=white)

### AI

![LLM](https://img.shields.io/badge/LLM-API-412991?style=flat-square)
![Optimization](https://img.shields.io/badge/Optimization-Greedy_Algorithm-orange?style=flat-square)

<br>

## 🗂 Data

- 🌡️ **기상청** — AWS · 기상예보
- 👴 **통계청 SGIS** — 고령인구 데이터
- 🌾 **농림수산식품교육문화정보원** — 팜맵 공간정보
- 🏠 **행정안전부** — 전국 무더위쉼터 표준데이터
- ☂️ **행정안전부** — 폭염저감시설 데이터
- 🗺️ **전국 법정구역 읍면동 경계**
- 🚑 **질병관리청** — 온열질환 발생 통계

<br>

## 🎯 MVP Scope

- 특정 농촌 시·군 **1개 지역**
- 폭염 대응시설 중 **무더위쉼터 1종**
- 직선거리 및 서비스 반경 기반 커버리지 분석
- 신규 쉼터 배치 추천 및 효과 비교
- AI 추천안과 사용자 배치안 비교

> ⚠️ 분석 결과는 실제 설치 위치를 확정하는 것이 아닌  
> **지자체 담당자의 우선 검토 및 의사결정을 지원하기 위한 정보**로 활용합니다.

<br>

## 👥 Team

| Role | Name |
|---|---|
| 개발 | 김해린 |
| 개발 | 유주원 |
| 개발 | 임정윤 |
| 기획 | 김수진 |
| 디자인 | 김민지 |
