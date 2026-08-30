import asyncio
import os

async def llm_normalize(q: str) -> tuple[str, float, str] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Normalize user query to canonical product search. Return JSON {\"canonical\": \"iphone 15 pro max 256\", \"category\": \"smartphone\", \"confidence\": 0.9}. Canonical must be latin, lowercase."},
                    {"role": "user", "content": q},
                ],
                temperature=0,
                max_tokens=80,
            ),
            timeout=0.8,
        )
        import json
        txt = resp.choices[0].message.content.strip()
        # extract json
        start = txt.find("{"); end = txt.rfind("}")+1
        data = json.loads(txt[start:end])
        return data["canonical"], float(data.get("confidence", 0.7)), data.get("category", "")
    except Exception:
        return None
