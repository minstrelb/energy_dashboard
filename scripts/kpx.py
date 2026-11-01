"""공공데이터포털(apis.data.go.kr)의 한국전력거래소 API 호출과 응답 읽기.

응답은 header / body(items → item) 구조이고, dataType 에 따라 JSON 또는 XML 로 온다.
어느 쪽이 와도 같은 모양(dict 목록)으로 돌려준다.

인증키는 환경변수 KPX_API_KEY 에서 읽는다. 코드·로그에 키를 남기지 않도록
오류 메시지에는 요청 주소(키가 들어 있음)를 넣지 않는다.
"""
import json
import os
import time
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import requests

BASE = "https://apis.data.go.kr/B552115"
URL_TODAY = f"{BASE}/Sukub5mToday/getSukub5mToday"                      # 오늘 5분 단위 전력수급 (XML)


class ApiError(RuntimeError):
    pass


def api_key():
    key = os.environ.get("KPX_API_KEY", "").strip()
    if not key:
        raise ApiError("환경변수 KPX_API_KEY 에 공공데이터포털 인증키를 넣어 주세요.")
    # Decoding·Encoding 어느 쪽 키를 붙여넣어도 requests 가 한 번만 인코딩하도록 푼다
    return unquote(key)


def parse(text):
    """응답 문자열 → (header dict, 전체 건수 또는 None, item dict 목록)"""
    t = text.strip()
    if t.startswith("{"):
        root = json.loads(t)
        root = root.get("response", root)
        header, body = root.get("header") or {}, root.get("body") or {}
        items = body.get("items")
        if isinstance(items, dict):
            items = items.get("item", [])
        total = body.get("totalCount")
    elif t.startswith("<"):
        root = ET.fromstring(t)
        err = root.find(".//cmmMsgHeader")        # 게이트웨이(키 오류·한도 초과 등)가 돌려주는 형식
        if err is not None:
            f = {c.tag: (c.text or "") for c in err}
            raise ApiError(f"{f.get('errMsg', '')}: {f.get('returnAuthMsg', '')} (코드 {f.get('returnReasonCode', '?')})")
        h = root.find(".//header")
        header = {c.tag: (c.text or "") for c in h} if h is not None else {}
        items = [{c.tag: (c.text or "").strip() for c in it} for it in root.findall(".//items/item")]
        total = root.findtext(".//body/totalCount")
    else:
        raise ApiError(f"JSON 도 XML 도 아닌 응답입니다: {t[:120]!r}")

    if not items:
        items = []
    elif isinstance(items, dict):
        items = [items]
    items = [i["item"] if isinstance(i, dict) and set(i) == {"item"} else i for i in items]
    return header, (int(total) if total not in (None, "") else None), items


def call(url, data_type="xml", retries=3, **params):
    """한 번 호출해서 parse() 결과를 돌려준다."""
    q = {"serviceKey": api_key(), "dataType": data_type, **params}
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=q, timeout=30)
        except requests.RequestException as e:
            err = f"연결 실패({type(e).__name__})"        # str(e) 에는 키가 든 주소가 있을 수 있어 쓰지 않는다
        else:
            if r.status_code < 500:
                if r.status_code >= 400:
                    raise ApiError(f"HTTP {r.status_code}: {r.text[:200]}")
                return parse(r.text)
            err = f"HTTP {r.status_code}"
        if attempt == retries:
            raise ApiError(f"요청 실패: {err}")
        time.sleep(2 * attempt)


def get_all(url, page_size=500, **params):
    """pageNo 를 올려 가며 전체 item 을 모은다."""
    out, page = [], 1
    while True:
        _, total, items = call(url, pageNo=page, numOfRows=page_size, **params)
        out += items
        if not items or total is None or len(out) >= total:
            return out
        page += 1
