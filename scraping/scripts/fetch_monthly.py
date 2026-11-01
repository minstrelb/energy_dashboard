"""EPSIS 연료원별 전력거래량(월별, 전력시장+PPA)을 받아 site/data/monthly_fuel.parquet 으로 저장한다.

  python scripts/fetch_monthly.py

한 번 요청하면 2002년 1월부터의 전체 기간이 오는 메뉴라서 매번 통째로 덮어쓴다.
단위는 GWh. 갱신 시기는 M+1월 말(예: 8월분은 9월 말)이고, 연간 확정 전까지 값이 바뀔 수 있다.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from epsis import parse_grid, post

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
OUT = DATA / "monthly_fuel.parquet"
META = DATA / "meta.json"

# 화면의 열 이름 -> 대시보드에서 쓸 이름 (석탄 = 유연탄+무연탄, 신재생 = 태양·풍력·수력 등 합계)
FUELS = {
    "c1": "원자력",
    "c23": "석탄",
    "c4": "유류",
    "c5": "LNG",
    "c6": "양수",
    "c912": "신재생",
    "c7": "기타",
    "c9": "PPA(태양광)",
}


def fetch() -> pd.DataFrame:
    # selRegion=1 은 '지역합계'(전국)
    text = post("selectEkmaPtdBft.ajax", {"selYear": "N", "selRegion": "1"})
    wide = pd.DataFrame(parse_grid(text))
    wide["month"] = pd.to_datetime(wide["Period"] + "/01", format="%Y/%m/%d").dt.date
    long = (
        wide.melt(id_vars="month", value_vars=list(FUELS), var_name="col", value_name="gwh")
        .assign(fuel=lambda d: d["col"].map(FUELS), gwh=lambda d: pd.to_numeric(d["gwh"], errors="coerce"))
        .drop(columns="col")
        .dropna(subset=["gwh"])
        .sort_values(["month", "fuel"])
        .reset_index(drop=True)
    )
    return long[["month", "fuel", "gwh"]]


def validate(df: pd.DataFrame) -> None:
    if df.empty:
        raise RuntimeError("받은 데이터가 없습니다.")
    if df.duplicated(["month", "fuel"]).any():
        raise RuntimeError("월·연료원이 중복되었습니다.")
    latest = df[df["month"] == df["month"].max()]
    total = latest["gwh"].sum()
    if not 20_000 < total < 120_000:  # 한 달 전력거래량은 대략 4~6만 GWh
        raise RuntimeError(f"최근 월 합계가 상식 범위를 벗어났습니다: {total:,.0f} GWh")


def main():
    new = fetch()
    validate(new)
    old = pd.read_parquet(OUT) if OUT.exists() else None
    if old is not None and new.equals(old.astype(new.dtypes.to_dict())):
        print(f"변경 없음 (마지막 월 {new['month'].max()})")
        return
    DATA.mkdir(parents=True, exist_ok=True)
    new.to_parquet(OUT, index=False)
    meta = json.loads(META.read_text()) if META.exists() else {}
    meta.update(monthly_last=str(new["month"].max()), monthly_rows=len(new),
                updated_at=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="minutes"))
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"저장: {OUT.name} {len(new):,}행, {new['month'].min()} ~ {new['month'].max()}")


if __name__ == "__main__":
    main()
