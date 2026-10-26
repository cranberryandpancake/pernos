from urllib.parse import unquote
import httpx

API = "https://aion2.plaync.com/api/character/info"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")

_client = httpx.AsyncClient(
    timeout=10.0,
    headers={"User-Agent": UA, "Accept": "application/json",
             "Referer": "https://aion2.plaync.com/ko-kr/characters"},
)


async def get_info(char_id: str, server_id):
    """캐릭터 레벨·전투력·직업 조회. 실패 시 None"""
    r = await _client.get(API, params={
        "lang": "ko",
        "characterId": unquote(char_id),   # 댓글 API 값이 이미 URL 인코딩돼 있음
        "serverId": server_id,
    })
    if r.status_code != 200:
        return None

    p = (r.json() or {}).get("profile")
    if not p:
        return None

    return {
        "level":  p["characterLevel"],
        "power":  p["combatPower"],
        "class":  p["className"],
        "name":   p["characterName"],
        "server": p["serverName"],
    }


async def close():
    await _client.aclose()