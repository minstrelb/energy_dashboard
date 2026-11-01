# 보류: 화면 뒤 주소로 받아 오는 방식 (스크래핑)

공식 API가 없는 자료(예: EPSIS 전력수급실적 일별, 연료원별 전력거래량 월별)를 **화면이 데이터를 받아 오는 비공식 주소**(`.ajax`)로 받아 오던 지난 준비물입니다.
이번 세션은 내용이 복잡해져 **API가 있는 자료만** 다루기로 해서 여기로 옮겨 두었습니다. 지우지 않았고, 아래대로 되돌리면 이전 상태로 돌아갑니다.

| 여기 있는 파일 | 원래 위치 |
|---|---|
| `scripts/epsis.py` `fetch_daily.py` `fetch_monthly.py` | `scripts/` |
| `data/daily_supply.parquet` `monthly_fuel.parquet` `meta.json` | `site/data/` |
| `dashboard_index.html` (일별 + 월별 연료원 대시보드) | `site/index.html` |
| `workflows/daily.yml` `monthly.yml` | `.github/workflows/` |
| `notebooks/workshop_scraping.ipynb` | `notebooks/workshop.ipynb` |

* 되돌리기 전에 지금의 `scripts/`, `site/`, `.github/workflows/daily.yml`, `notebooks/workshop.ipynb` 와 이름이 겹치니 먼저 옮겨 두세요. 두 방식의 `site/data/meta.json` 모양도 다릅니다.
* 이 방식은 **비공식**이라 EPSIS 화면이 바뀌면 깨질 수 있습니다. 스크립트는 응답이 비거나 값이 상식 범위를 벗어나면 멈추게 되어 있습니다.
* 지난 준비물에서 확인한 것: 일별 수급실적 2022-01-01~2026-10-29(1,763행), 월별 연료원별 거래량 2002-01~2026-08. 로컬(한국)에서만 실행해 봤고 **GitHub Actions·Colab에서의 접속은 시험하지 못했습니다.**
* 일별 수급실적에는 같은 값이 두 번 들어 있는 열흘(2023-04-01~10)이 있어 `fetch_daily.py` 가 완전히 같은 행만 제거합니다.
* 최소전력은 2025-11-24 이전 값이 없습니다(EPSIS 안내).
