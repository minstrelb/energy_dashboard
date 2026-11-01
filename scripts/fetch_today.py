"""오늘의 5분 단위 전력수급을 받아 site/data/supply_5min.parquet 에 쌓는다.

공공데이터포털 「한국전력거래소_오늘전력수급현황조회_GW」는 '오늘' 하루치만 돌려준다.
어제 값은 다시 받을 수 없으므로, 이 스크립트를 매일 돌려 파일에 쌓아 두는 것이 자동화의 핵심이다.

* 같은 시각(ts)이 이미 있으면 새로 받은 값으로 덮어쓴다 → 하루에 몇 번 돌려도 중복이 생기지 않는다.
* 받은 값이 상식 범위를 벗어나거나 비어 있으면 오류로 멈춘다 (Actions 가 빨간 X 로 알려 준다).
* 쌓인 내용이 그대로면 파일을 건드리지 않는다.

사용법:  KPX_API_KEY=<인증키> python scripts/fetch_today.py
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import kpx

OUT_DIR = Path(__file__).resolve().parents[1] / "site" / "data"
OUT = OUT_DIR / "supply_5min.parquet"
META = OUT_DIR / "meta.json"

# API 항목 → 표 열 이름 (전부 MW, 예비율만 %)
COLUMNS = {
    "baseDatetime": "ts",
    "currPwrTot": "demand_mw",        # 현재수요
    "suppAbility": "supply_mw",       # 공급능력
    "forecastLoad": "forecast_mw",    # 최대예측수요
    "suppReservePwr": "reserve_mw",   # 공급예비력
    "suppReserveRate": "reserve_pct",   # 공급예비율
    "operReservePwr": "oper_reserve_mw",   # 운영예비력
    "operReserveRate": "oper_reserve_pct",  # 운영예비율
}
KST = timezone(timedelta(hours=9))


def to_frame(items):
    if not items:
        raise SystemExit("받은 데이터가 비어 있습니다. 자정 직후이거나 API 점검 중일 수 있습니다.")
    df = pd.DataFrame(items)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"응답에 예상한 항목이 없습니다: {missing}\n받은 항목: {list(df.columns)}")
    df = df[list(COLUMNS)].rename(columns=COLUMNS)
    # 기준일시는 '년월일시분초' — 숫자만 남기면 20261031143000 / 2026-10-31 14:30:00 어느 모양이든 읽힌다
    digits = df["ts"].astype(str).str.replace(r"\D", "", regex=True).str.ljust(14, "0").str[:14]
    df["ts"] = pd.to_datetime(digits, format="%Y%m%d%H%M%S", errors="coerce")
    for c in df.columns.drop("ts"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    return df


def validate(df):
    if df.empty:
        raise SystemExit("받은 데이터가 비어 있습니다. 자정 직후이거나 API 점검 중일 수 있습니다.")
    if df["ts"].isna().any():
        raise SystemExit("기준일시를 읽지 못한 행이 있습니다.")
    if df["ts"].duplicated().any():
        raise SystemExit("같은 시각이 여러 번 들어 있습니다.")
    lo, hi = df["demand_mw"].min(), df["demand_mw"].max()
    if lo < 10_000 or hi > 150_000:      # 우리나라 전력수요는 대략 4만~10만 MW
        raise SystemExit(f"현재수요가 상식 범위(1만~15만 MW)를 벗어났습니다: {lo:,.0f} ~ {hi:,.0f}")


def normalize(df):
    df = df.copy()
    df["ts"] = df["ts"].astype("datetime64[ns]")
    for c in df.columns.drop("ts"):
        df[c] = df[c].astype("float64")
    return df.sort_values("ts").reset_index(drop=True)


def main():
    items = kpx.get_all(kpx.URL_TODAY, data_type="xml")
    new = to_frame(items)

    # 아직 오지 않은 시각의 행은 수요가 비어 있거나 0 일 수 있다 → 실적이 있는 행만 쌓는다
    observed = new["demand_mw"].notna() & (new["demand_mw"] > 0)
    if not observed.all():
        print(f"실적이 없는 행 {int((~observed).sum())}개는 제외합니다.")
    new = new[observed]
    validate(new)
    print(f"받은 행: {len(new)}개 ({new['ts'].min():%Y-%m-%d %H:%M} ~ {new['ts'].max():%H:%M})")

    old = normalize(pd.read_parquet(OUT)) if OUT.exists() else None
    merged = new if old is None else pd.concat([old, new])
    merged = normalize(merged.drop_duplicates("ts", keep="last"))     # 같은 시각은 새 값으로

    if old is not None and merged.equals(old):
        print("변경 없음")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUT, index=False, coerce_timestamps="ms")
    META.write_text(json.dumps({
        "updated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "rows": len(merged),
        "days": int(merged["ts"].dt.normalize().nunique()),
        "first_ts": f"{merged['ts'].min():%Y-%m-%dT%H:%M}",
        "last_ts": f"{merged['ts'].max():%Y-%m-%dT%H:%M}",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    added = len(merged) - (0 if old is None else len(old))
    print(f"저장: 총 {len(merged):,}행 (+{added}) → site/data/{OUT.name}")


if __name__ == "__main__":
    main()
