"""Currency helper — актуальный курс RUB→BYN с NBRB (Национальный банк РБ).

NBRB API: GET https://api.nbrb.by/exrates/rates/RUB?parammode=2
→ {"Cur_OfficialRate": 3.5617, "Cur_Scale": 100, "Date": "2026-08-30T00:00:00"}
означает 100 RUB = 3.5617 BYN → 1 RUB = 0.035617 BYN

Кеш 6 часов, fallback 0.035617 (актуальный на 2026-08-30), чтобы не падать если NBRB недоступен.
"""

import asyncio
import time

# актуальный на 2026-08-30, обновляется при каждом успешном fetch
FALLBACK_RUB_TO_BYN = 0.035617

_cache_value: float | None = None
_cache_ts: float = 0
_cache_lock = asyncio.Lock()
TTL_SEC = 6 * 3600


async def get_rub_to_byn() -> float:
    global _cache_value, _cache_ts
    now = time.monotonic()
    if _cache_value is not None and (now - _cache_ts) < TTL_SEC:
        return _cache_value

    async with _cache_lock:
        # double-check после lock
        now = time.monotonic()
        if _cache_value is not None and (now - _cache_ts) < TTL_SEC:
            return _cache_value
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=4)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get("https://api.nbrb.by/exrates/rates/RUB?parammode=2") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rate = float(data.get("Cur_OfficialRate", 0))
                        scale = int(data.get("Cur_Scale", 100))
                        if rate > 0 and scale > 0:
                            val = rate / scale
                            _cache_value = val
                            _cache_ts = time.monotonic()
                            return val
        except Exception:
            pass
        # fallback
        if _cache_value is not None:
            return _cache_value
        return FALLBACK_RUB_TO_BYN


def get_rub_to_byn_sync() -> float:
    """Синхронная версия для thread-pool (wildberries). Кеш без lock, ок для MVP."""
    if _cache_value is not None and (time.monotonic() - _cache_ts) < TTL_SEC:
        return _cache_value
    # пытаемся синхронно дернуть NBRB через curl_cffi / urllib
    try:
        import urllib.request, json
        with urllib.request.urlopen("https://api.nbrb.by/exrates/rates/RUB?parammode=2", timeout=4) as r:
            data = json.loads(r.read().decode())
            rate = float(data.get("Cur_OfficialRate", 0))
            scale = int(data.get("Cur_Scale", 100))
            if rate > 0 and scale > 0:
                return rate / scale
    except Exception:
        pass
    return _cache_value if _cache_value is not None else FALLBACK_RUB_TO_BYN
