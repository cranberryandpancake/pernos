import httpx

import os

BOARD = os.getenv("BOARD_ALIAS", "server_ko")
BASE = f"https://api-community.plaync.com/aion2/board/{BOARD}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")

_client = httpx.AsyncClient(
    timeout=10.0,
    headers={"User-Agent": UA, "Accept": "application/json"},
)


def _parse(item):
    m = item["contentMeta"]
    g = m["writer"]["gameUser"]
    return {
        "cursor":    m["snow"]["contentId"],
        "text":      item["content"]["content"],
        "name":      g["gameCharacterName"],
        "server_id": g["gameServerId"],
        "origin_id": g["gameCharacterOriginId"],
        "char_id": g["gameCharacterId"],
        "posted":    m["timestamps"]["postedEpoch"],
    }


async def fetch_page(article_id, cursor=0, size=100):
    """최신순으로 댓글 한 페이지"""
    r = await _client.get(
        f"{BASE}/article/{article_id}/comment/search/moreComment",
        params={
            "moreSize": size,
            "moreDirection": "BEFORE",
            "previousCommentId": cursor,
            "orderType": "desc",
        },
    )
    r.raise_for_status()
    j = r.json()
    return [_parse(i) for i in j["contentList"]], j["hasMore"]


def _norm(s: str) -> str:
    """대소문자·공백·줄바꿈 무시하고 비교하기 위한 정규화"""
    return "".join(s.split()).upper()


async def find_code(article_id, code, issued_at, max_pages=3):
    """issued_at(epoch초) 이후에 달린 댓글에서만 code를 찾는다"""
    target = _norm(code)
    cursor = 0
    for _ in range(max_pages):
        items, more = await fetch_page(article_id, cursor)
        if not items:
            return None
        for it in items:
            if it["posted"] < issued_at:
                return None          # 최신순이라 여기부터는 전부 과거 → 중단
            if target in _norm(it["text"]):
                return it
        if not more:
            return None
        cursor = items[-1]["cursor"]
    return None


async def close():
    await _client.aclose()