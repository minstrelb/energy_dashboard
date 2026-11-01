# 한국 전력수급 대시보드: API 자동 수집 실습 세션 자료

지난 지식공유 세션(분석 대시보드 구동 방식: Parquet · DuckDB-Wasm · Netlify)의 후속 **실습 세션** 자료입니다.

이번 세션은 **공식 API가 있는 자료만** 다룹니다. (화면에서 긁어오는 방식은 내용이 복잡해져 보류했고, 관련 자료들은 [`extras/scraping/`](extras/scraping/README.md)에 남겨 두었습니다.)

```
[매일] GitHub Actions → scripts/fetch_today.py 가 공공데이터포털 API 호출 → site/data/supply_5min.parquet 에 쌓고 커밋
        → 같은 워크플로가 site/ 를 GitHub Pages 에 배포 → 링크를 여는 브라우저가 DuckDB-Wasm 으로 계산해서 그래프를 그림
```

**핵심 메시지:** 이 API는 '오늘'만 알려 줍니다. 어제 값은 다시 받을 수 없으니 **매일 받아서 쌓는 일**이 곧 자동화입니다.

## 쓰는 데이터

### 1. 받아 오는 데이터: 공공데이터포털 · 한국전력거래소 API (이용허락범위 제한 없음, 무료)

| | 한국전력거래소_오늘전력수급현황조회_GW |
|---|---|
| 상세 페이지 | [15158703](https://www.data.go.kr/data/15158703/openapi.do) |
| 주소 | `apis.data.go.kr/B552115/Sukub5mToday/getSukub5mToday` |
| 페이지의 설명 | "오늘의 전력수급현황" |
| 이 자료에서 기대하는 응답 ※ | 오늘 0시부터 지금까지 5분 단위 여러 건 |
| 형식 | 페이지에는 XML (`dataType` 은 xml/json 둘 다 안내). 코드는 XML 사용 |
| 요청변수 | `serviceKey`\* `dataType`\* `pageNo` `numOfRows` |

\* 필수. ※ 행은 API 페이지가 아니라 명세와 연습 흐름에 맞춰 적은 기대값입니다. 페이지에는 위 "페이지의 설명" 정도만 있어서, **실제 호출로 확인하기 전까지는 가정**입니다. 

* 응답 항목(단위 MW): `baseDatetime` 기준일시 · `currPwrTot` 현재수요 · `suppAbility` 공급능력 · `forecastLoad` 최대예측수요 · `suppReservePwr` 공급예비력 · `suppReserveRate` 공급예비율(%) · `operReservePwr` 운영예비력 · `operReserveRate` 운영예비율(%). 페이지에는 한글 항목명만 있어 영문 태그 이름은 명세 기준이며 호출로 확인이 필요합니다.
* 이 API는 **2026-06-30에 기존 PUBC 방식에서 GW 방식으로 바뀌었습니다**(API 페이지에 공지). 예전 블로그·예제의 주소는 동작하지 않을 수 있습니다.
* 과거 자료: 한국전력거래소 「현재전력수급현황조회」 페이지가 안내하는 파일 내려받기(https://openapi.kpx.or.kr/sukub.do, 3개월 단위)가 있습니다. 

### 2. 쌓는 데이터: `site/data/`

`fetch_today.py` 가 위 '오늘' API의 응답을 아래 열로 바꿔 `supply_5min.parquet` 에 쌓습니다. 대시보드와 노트북의 SQL 표 이름은 `supply` 입니다.

| 열 | API 항목 | 뜻 | 단위 |
|---|---|---|---|
| `ts` | `baseDatetime` | 기준일시 (5분 간격) | KST |
| `demand_mw` | `currPwrTot` | 현재수요 | MW |
| `supply_mw` | `suppAbility` | 공급능력 | MW |
| `forecast_mw` | `forecastLoad` | 최대예측수요 | MW |
| `reserve_mw` / `reserve_pct` | `suppReservePwr` / `suppReserveRate` | 공급예비력 / 공급예비율 | MW / % |
| `oper_reserve_mw` / `oper_reserve_pct` | `operReservePwr` / `operReserveRate` | 운영예비력 / 운영예비율 | MW / % |

* `ts` 가 기본키 역할입니다. 같은 시각은 새 값으로 덮어쓰고, 수요가 비었거나 0인 행(아직 오지 않은 시각)은 쌓지 않습니다.
* 기준일시는 숫자만 남겨 읽으므로 `20261031143000` 이든 `2026-10-31 14:30:00` 이든 받아들입니다.
* `meta.json` 에는 수집 시각(`updated_at`), 행 수(`rows`), 일 수(`days`), 처음·마지막 시각(`first_ts`, `last_ts`)이 들어갑니다. 계산 재료는 Parquet, 참고 정보는 JSON으로 나눈 것입니다.
* 첫 수집 전에는 `site/data/` 가 없습니다.

## 폴더 구성

```
energy-dashboard/
├─ site/                       ← GitHub Pages 가 그대로 나눠주는 폴더
│  ├─ index.html               대시보드 (DuckDB-Wasm + Plotly, SQL 실습창 포함)
│  └─ data/                    supply_5min.parquet · meta.json  (첫 수집 후에 생김)
├─ scripts/
│  ├─ kpx.py                   API 호출 + JSON/XML 응답 읽기 (키는 환경변수 KPX_API_KEY)
│  └─ fetch_today.py           오늘 5분 데이터를 받아 검증하고 파일에 쌓기
├─ notebooks/workshop.ipynb    참가자용 Colab 노트북 (연습문제 + 정답 접기)
├─ .github/workflows/daily.yml 매일 22:17 · 23:37 KST 에 수집하고 GitHub Pages 에 배포
├─ extras/scraping/            보류: 화면 뒤 주소를 찾아 받아 오는 방식의 지난 준비물
└─ requirements.txt            requests · pandas · pyarrow
```


## 알아둘 점

* **아직 오지 않은 시각의 행**이 수요 0이나 빈 값으로 올 수 있다고 가정하고, `fetch_today.py` 는 실적이 있는 행만 쌓습니다. 실제 응답에서 확인해 주세요.
* **값이 이상하면 멈춥니다.** 비었거나, 시각을 못 읽거나, 현재수요가 1만~15만 MW 밖이면 오류로 끝나고 Actions가 빨간 X로 알려 줍니다. 같은 시각이 이미 있으면 새 값으로 덮어쓰므로 여러 번 돌려도 중복이 없습니다.
* **인증키는 코드에 쓰지 않습니다.** 환경변수(`KPX_API_KEY`)로만 읽고, 오류 메시지에도 요청 주소(키가 들어 있음)를 넣지 않습니다. 노트북은 `getpass` 입력창을 씁니다. Encoding 키를 붙여넣어도 `unquote` 로 풀어서 이중 인코딩을 피합니다.
* **저장소가 조금씩 커집니다.** 하루 두 번 파일이 바뀌어 커밋됩니다. 1년이면 파일 자체는 수 MB 안팎으로 보이지만(추정), 장기 운영하려면 월별로 파일을 나누는 것을 고려하세요.
* **배포는 GitHub Pages입니다.** 수집 → 커밋 → 배포가 한 워크플로(`daily.yml`)에서 이어집니다. (Netlify 무료 플랜은 배포 1회에 15크레딧, 월 300크레딧이라 하루 두 번 배포하면 한도에 닿아서 바꿨습니다. 
  * 무료로 쓰려면 **공개 저장소**여야 합니다. 비공개 저장소의 Pages는 유료 플랜에서만 되는 것으로 알고 있으니 확인하세요. 코드와 수집한 데이터가 공개된다는 뜻이기도 합니다.
  * 대시보드(`site/index.html`)를 고친 뒤에는 *Run workflow* 에서 **collect 체크를 끄고** 실행해 다시 배포하세요. (push 만으로는 배포되지 않습니다.)
  * Netlify처럼 캐시 헤더를 직접 정할 수 없어, 갱신이 몇 분 늦게 보일 수 있습니다.
* 공개 저장소는 60일간 활동이 없으면 예약 실행(cron)이 꺼질 수 있습니다.
* 출처 표기(한국전력거래소, 공공데이터포털)는 대시보드 하단에 들어 있습니다.

## 이 자료와 지난 세션의 연결

| 지난 세션 (분석 대시보드 구동 방식) | 이번 실습 |
|---|---|
| SQL = DB 에게 보내는 주문서, pandas 와 같은 일 (5쪽) | Part 4 에서 pandas / SQL 나란히 실행 |
| Parquet = 계산 재료, JSON = 참고 정보 (12쪽) | 5분 수급값은 조건에 따라 달라지는 값이므로 Parquet. 수집 시각 같은 메타 정보(`meta.json`)는 JSON |
| DuckDB-Wasm + Netlify, 서버 없이 브라우저가 계산 (14쪽) | 같은 구조의 `site/index.html` (호스팅만 GitHub Pages) |
| 내 컴퓨터 → GitHub push → Netlify (16쪽) | 그 앞에 **GitHub Actions 가 API를 호출해 push 를 대신해 주는 단계**를 추가하고, 배포도 같은 워크플로가 GitHub Pages 로 합니다 |