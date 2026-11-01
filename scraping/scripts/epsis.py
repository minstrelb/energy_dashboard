"""EPSIS(전력통계정보시스템) 화면이 쓰는 데이터 주소에서 값을 받아오는 함수 모음.

EPSIS는 공식 Open API가 없는 메뉴가 많아서, 사이트 화면이 내부적으로 호출하는 주소
(개발자도구 > Network 탭에서 보이는 *.ajax)를 직접 호출한다. 응답은 JSON이 아니라
`gridData.push({...})` 형태의 자바스크립트 코드라서 정규식으로 값을 뽑는다.

사이트가 개편되면 깨질 수 있으므로 parse_grid() 결과가 비어 있으면 바로 오류를 낸다.
"""
import re
import time

import requests

BASE = "https://epsis.kpx.or.kr/epsisnew"
HEADERS = {"User-Agent": "energy-dashboard-workshop/1.0 (educational, once-a-day requests)"}

# 한 블록 안에서 `c4 = textFormmat("70319.0",count);` 처럼 값이 대입되는 줄
_ASSIGN = re.compile(r'\b(c\d+|localnm|year)\s*=\s*(?:textFormmat\()?\(?"([^"]*)"')
# push({...}) 안의 "키": "값" 또는 "키": 변수이름
_PAIR = re.compile(r'"(\w+)"\s*:\s*(?:"([^"]*)"|(\w+))')


def post(path: str, data: dict, retries: int = 3) -> str:
    """EPSIS에 POST 요청을 보내고 본문 텍스트를 돌려준다. 실패하면 잠깐 쉬었다 다시 시도."""
    last = None
    for i in range(retries):
        try:
            r = requests.post(f"{BASE}/{path}", data=data, headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"EPSIS 요청 실패: {path} ({last})")


def parse_grid(text: str) -> list[dict]:
    """응답 속 gridData.push(...) 블록을 dict 리스트로 바꾼다."""
    parts = re.split(r"gridData\.push\(", text)
    rows = []
    pending = parts[0]  # 첫 블록의 값 대입문은 첫 push 앞에 있다
    for part in parts[1:]:
        body, _, after = part.partition("})")
        values = dict(_ASSIGN.findall(pending))
        row = {}
        for m in _PAIR.finditer(body):
            key, literal, var = m.group(1), m.group(2), m.group(3)
            row[key] = literal if literal is not None else values.get(var)
        rows.append(row)
        pending = after  # 다음 블록의 값 대입문은 이번 push 뒤에 있다
    if not rows:
        raise RuntimeError("EPSIS 응답에서 데이터를 찾지 못했습니다. 사이트 구조가 바뀌었는지 확인하세요.")
    return rows
