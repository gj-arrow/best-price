import asyncio
import os
import json
import urllib.parse

# Pollinations — бесплатно, без ключа, hosting-friendly (чистый HTTP)
# Fallback: HuggingFace если задан HF_TOKEN
POLLINATIONS_URL = "https://text.pollinations.ai"

async def _pollinations_normalize(q: str) -> tuple[str, float, str] | None:
    try:
        import aiohttp, ssl, certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        prompt = (
            f'Normalize shop query "{q}" to canonical product name. '
            'Return ONLY JSON like {"canonical":"iphone 15 pro max 256","category":"smartphone","confidence":0.95}. '
            'Canonical must be latin lowercase, correct brand/model, fix cyrillic and typos. '
            'Category one of smartphone,tv,vacuum,laptop,tablet,headphones,watch,fridge,other.'
        )
        url = f"{POLLINATIONS_URL}/{urllib.parse.quote(prompt)}?model=openai&json=true"
        timeout = aiohttp.ClientTimeout(total=4)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as sess:
            async with sess.get(url) as resp:
                if resp.status != 200:
                    return None
                txt = await resp.text()
                # Pollinations с ?json=true уже возвращает JSON, но может быть обёртка
                try:
                    data = json.loads(txt)
                    # если пришёл {"choices":...} не ожидается, парсим как текст
                    if "canonical" in data:
                        return data["canonical"].lower().strip(), float(data.get("confidence", 0.9)), data.get("category", "")
                except json.JSONDecodeError:
                    pass
                start = txt.find("{"); end = txt.rfind("}") + 1
                if start == -1 or end == 0:
                    return None
                data = json.loads(txt[start:end])
                canon = data.get("canonical") or data.get("query") or data.get("result") or ""
                if not canon:
                    return None
                return canon.lower().strip(), float(data.get("confidence", 0.9)), data.get("category", "")
    except Exception:
        return None

async def _hf_normalize(q: str) -> tuple[str, float, str] | None:
    token = os.getenv("HF_TOKEN")
    if not token:
        return None
    try:
        import aiohttp, ssl, certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
        headers = {"Authorization": f"Bearer {token}"}
        prompt = f'[INST] Normalize "{q}" to JSON {{"canonical":"...","category":"...","confidence":0.9}} canonical latin lowercase [/INST]'
        timeout = aiohttp.ClientTimeout(total=4)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as sess:
            async with sess.post(url, headers=headers, json={"inputs": prompt, "parameters": {"max_new_tokens": 80, "temperature": 0.0}}) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                txt = data[0]["generated_text"] if isinstance(data, list) else str(data)
                start = txt.find("{"); end = txt.rfind("}") + 1
                if start == -1:
                    return None
                j = json.loads(txt[start:end])
                return j["canonical"].lower().strip(), float(j.get("confidence", 0.85)), j.get("category", "")
    except Exception:
        return None

async def _openrouter_normalize(q: str) -> tuple[str, float, str] | None:
    token = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY")
    if not token:
        return None
    try:
        import aiohttp, ssl, certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "HTTP-Referer": "https://best-price.by",
            "X-Title": "BestPrice Search",
            "Content-Type": "application/json",
        }
        body = {
            "model": "minimax/minimax-m3:free",
            "messages": [
                {"role": "system", "content": 'You normalize shop search queries. Return ONLY JSON {"canonical":"...","category":"smartphone|tv|vacuum|laptop|tablet|headphones|watch|fridge|other","confidence":0.95}. Canonical latin lowercase, fix cyrillic and typos, expand brand.'},
                {"role": "user", "content": q},
            ],
            "temperature": 0,
            "max_tokens": 80,
        }
        # fallback если rate-limited
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as sess:
            async with sess.post(url, headers=headers, json=body) as resp:
                if resp.status == 429:
                    # OpenRouter returns 429 for rate-limited upstream — retry with another free model after Retry-After
                    retry_after = 2
                    try:
                        j2 = await resp.json()
                        retry_after = int(j2.get("error", {}).get("metadata", {}).get("retry_after_seconds", 2))
                    except: pass
                    await asyncio.sleep(min(retry_after, 5))
                    body["model"] = "google/gemma-4-26b-a4b-it:free"
                    async with sess.post(url, headers=headers, json=body) as r2:
                        if r2.status != 200:
                            return None
                        data = await r2.json()
                        txt = data["choices"][0]["message"]["content"].strip()
                        start = txt.find("{"); end = txt.rfind("}") + 1
                        if start == -1:
                            return None
                        j = json.loads(txt[start:end])
                        return j["canonical"].lower().strip(), float(j.get("confidence", 0.9)), j.get("category", "")
                if resp.status != 200:
                    return None
                data = await resp.json()
                txt = data["choices"][0]["message"]["content"].strip()
                start = txt.find("{"); end = txt.rfind("}") + 1
                if start == -1:
                    return None
                j = json.loads(txt[start:end])
                canon = j.get("canonical") or ""
                if not canon:
                    return None
                return canon.lower().strip(), float(j.get("confidence", 0.9)), j.get("category", "")
    except Exception:
        return None

async def llm_normalize(q: str) -> tuple[str, float, str] | None:
    # 0) OpenRouter free — основной (hosting-friendly, без очереди, free)
    res = await _openrouter_normalize(q)
    if res:
        return res
    # 1) Pollinations (free, без ключа) — fallback, queue 1/ IP
    res = await _pollinations_normalize(q)
    if res:
        return res
    # 2) HuggingFace fallback если задан HF_TOKEN
    res = await _hf_normalize(q)
    if res:
        return res
    # 3) OpenAI fallback если вдруг есть ключ (совместимость)
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
    if api_key and "gsk_" not in api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": 'Normalize shop query to JSON {"canonical":"iphone 15 pro max 256","category":"smartphone","confidence":0.9} canonical latin lowercase.'},
                        {"role": "user", "content": q},
                    ],
                    temperature=0, max_tokens=80,
                ), timeout=1.0)
            txt = resp.choices[0].message.content.strip()
            start = txt.find("{"); end = txt.rfind("}")+1
            data = json.loads(txt[start:end])
            return data["canonical"].lower().strip(), float(data.get("confidence", 0.7)), data.get("category", "")
        except Exception:
            pass
    return None
