"""EPSIS 전력수급실적(일별)을 받아 site/data/daily_supply.parquet 에 쌓는다.

  python scripts/fetch_daily.py                    # 마지막 날짜 14일 전부터 다시 받아 덮어쓰기
  python scripts/fetch_daily.py --start 2022-01-01 # 처음부터 다시 받기

단위: 설비용량·공급능력·최대/최소전력·공급예비력은 MW, 공급예비율은 %.
최소전력은 2025-11-24 이전 값이 제공되지 않아 비어 있다(NaN).
"""
import argparse
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from epsis import parse_grid, post

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
OUT = DATA / "daily_supply.parquet"
META = DATA / "meta.json"
DEFAULT_START = date(2022, 1, 1)
OVERLAP_DAYS = 14  # 최근 값은 나중에 고쳐질 수 있어서 겹쳐서 다시 받는다

COLUMNS = {
    "c1": "capacity_mw",   # 설비용량
    "c3": "supply_mw",     # 공급능력
    "c4": "peak_mw",       # 최대전력
    "c8": "min_mw",        # 최소전력
    "c5": "reserve_mw",    # 공급예비력
    "c6": "reserve_pct",   # 공급예비율
}


def _hour(text):
    """'2026/10/28(19:00)' -> 19"""
    m = re.search(r"\((\d{1,2}):", text or "")
    return int(m.group(1)) if m else None


def fetch(begin: date, end: date) -> pd.DataFrame:
    text = post("selectEkgeEpsMep.ajax", {
        "beginDate": begin.strftime("%Y%m%d"),
        "endDate": end.strftime("%Y%m%d"),
        "selYear": "",
        "selMonth": "",
    })
    df = pd.DataFrame(parse_grid(text))
    out = pd.DataFrame({
        "date": pd.to_datetime(df["year"] + df["month"] + df["day"], format="%Y%m%d").dt.date,
    })
    for src, dst in COLUMNS.items():
        out[dst] = pd.to_numeric(df[src], errors="coerce")
    out["peak_hour"] = df["c7"].map(_hour).astype("Int64")
    out["min_hour"] = df["c9"].map(_hour).astype("Int64")
    out.loc[out["min_mw"] == 0, "min_mw"] = None  # 0은 '값 없음'으로 내려온다
    # 원본에 2023-04-01~10 열흘치가 똑같은 값으로 두 번 들어 있다 -> 완전히 같은 행만 제거
    # (값이 다른 중복은 validate()에서 오류로 잡는다)
    out = out.drop_duplicates()
    return out.sort_values("date").reset_index(drop=True)


def validate(df: pd.DataFrame) -> None:
    if df.empty:
        raise RuntimeError("받은 데이터가 없습니다.")
    if df["date"].duplicated().any():
        raise RuntimeError("날짜가 중복되었습니다.")
    bad = df[(df["peak_mw"] < 30_000) | (df["peak_mw"] > 120_000)]
    if not bad.empty:
        raise RuntimeError(f"최대전력이 상식 범위(3~12만 MW)를 벗어난 날이 있습니다:\n{bad.head()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat, help="이 날짜부터 받기 (기본: 기존 데이터 마지막 날짜 - 14일)")
    args = ap.parse_args()

    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    old = pd.read_parquet(OUT) if OUT.exists() else None
    if args.start:
        start = args.start
    elif old is not None:
        start = max(old["date"]) - timedelta(days=OVERLAP_DAYS)
    else:
        start = DEFAULT_START

    new = fetch(start, today)
    merged = new if old is None else pd.concat(
        [old[old["date"] < start], new], ignore_index=True
    ).sort_values("date").reset_index(drop=True)
    validate(merged)

    if old is not None and merged.equals(old.astype(merged.dtypes.to_dict())):
        print(f"변경 없음 (마지막 날짜 {merged['date'].max()})")
        return

    DATA.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(OUT, index=False)
    meta = json.loads(META.read_text()) if META.exists() else {}
    meta.update(daily_last=str(merged["date"].max()), daily_rows=len(merged),
                updated_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="minutes"))
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"저장: {OUT.name} {len(merged):,}행, {merged['date'].min()} ~ {merged['date'].max()}")


if __name__ == "__main__":
    main()
