import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
try:
    from backend.database import get_db, async_session
    from backend.models import Search, Product
    from backend.schemas import SearchResult, ProductResponse, QueryMeta
    from backend.scrapers.aggregator import ScraperAggregator
    from backend.normalizer.query_normalizer import QueryNormalizer
    from backend.filter.post_filter import filter_products
except ModuleNotFoundError:
    from database import get_db, async_session  # type: ignore
    from models import Search, Product  # type: ignore
    from schemas import SearchResult, ProductResponse, QueryMeta  # type: ignore
    from scrapers.aggregator import ScraperAggregator  # type: ignore
    from normalizer.query_normalizer import QueryNormalizer  # type: ignore
    from filter.post_filter import filter_products  # type: ignore

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/rate")
async def get_rate():
    """Текущий курс RUB→BYN с NBRB (кеш 6ч). Используется для конвертации Wildberries."""
    try:
        from utils.currency import get_rub_to_byn
    except ModuleNotFoundError:
        from backend.utils.currency import get_rub_to_byn  # type: ignore
    rate = await get_rub_to_byn()
    return {"rub_to_byn": rate, "byn_to_rub": 1 / rate if rate else None}


@router.get("/search", response_model=SearchResult)
async def search_products(
    q: str,
    include_kufar: bool = False,
    no_correct: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    normalizer = QueryNormalizer(db=db)
    norm = await normalizer.normalize(q, no_correct=no_correct)
    canonical = norm.canonical

    search = Search(query=q)  # храним original
    db.add(search)
    await db.commit()
    await db.refresh(search)

    # original-first: сначала ищем как ввёл юзер, фолбэк на canonical если пусто
    aggregator = ScraperAggregator(include_kufar=include_kufar)
    try:
        # 1) original
        products_data = await aggregator.search_all(q, include_kufar=include_kufar)
        debug = getattr(aggregator, "_last_debug", None)
        filtered = filter_products(q, products_data)
        # 2) если ничего и canonical отличается — пробуем canonical
        if not filtered and canonical.strip().lower() != q.strip().lower():
            # даём вторую попытку с нормализованным запросом
            products_data2 = await aggregator.search_all(canonical, include_kufar=include_kufar)
            debug2 = getattr(aggregator, "_last_debug", None)
            filtered2 = filter_products(canonical, products_data2)
            if filtered2:
                filtered = filtered2
                # мерджим debug для прозрачности
                if debug and debug2:
                    debug = debug + [{"store": d["store"] + " (canon)", **{k: v for k, v in d.items() if k != "store"}} for d in debug2]
                else:
                    debug = debug2
    finally:
        await aggregator.close()

    db_products = [Product(search_id=search.id, name=p.name, price=p.price, store=p.store, url=p.url) for p in filtered]
    db.add_all(db_products)
    await db.commit()

    response_products = [ProductResponse(id=0, name=p.name, price=p.price, store=p.store, url=p.url, is_best_price=(i==0)) for i, p in enumerate(filtered)]
    prices = [p.price for p in filtered]
    query_meta = QueryMeta(original=norm.original, canonical=norm.canonical, corrected=norm.corrected, confidence=norm.confidence, category=norm.category)
    if not filtered:
        return SearchResult(query=q, products=[], min_price=0, max_price=0, total_results=0, query_meta=query_meta, debug=debug)
    return SearchResult(query=q, products=response_products[:30], min_price=min(prices), max_price=max(prices), total_results=len(filtered), query_meta=query_meta, debug=debug)


@router.get("/search/stream")
async def search_stream(
    q: str,
    include_kufar: bool = False,
    no_correct: bool = Query(default=False),
):
    """Streaming search — выдаёт результаты по мере готовности магазинов (SSE).

    События:
      start {query, canonical, stores}
      store {store, status: ok|empty|error, found, error?, products: [{name,price,store,url}]}
      done  {total_results, min_price, max_price, query_meta, debug}
    Фронт использует EventSource/fetch streaming для инкрементального рендера.
    """
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    async def event_gen():
        # нормируем запрос (отдельная сессия)
        async with async_session() as db:
            normalizer = QueryNormalizer(db=db)
            norm = await normalizer.normalize(q, no_correct=no_correct)
            canonical = norm.canonical
            query_meta = {
                "original": norm.original,
                "canonical": norm.canonical,
                "corrected": norm.corrected,
                "confidence": norm.confidence,
                "category": norm.category,
            }
            # лог поиска
            try:
                search = Search(query=q)
                db.add(search)
                await db.commit()
                search_id = search.id
            except Exception:
                await db.rollback()
                search_id = None
        # original-first: пробуем как ввёл юзер, фолбэк на canonical если пусто
        tmp_agg = ScraperAggregator(include_kufar=include_kufar)
        scrapers_to_run = list(tmp_agg.scrapers)
        if include_kufar:
            scrapers_to_run.append(tmp_agg._kufar)
        store_names = [getattr(s, "store_name", s.__class__.__name__) for s in scrapers_to_run]
        yield f"data: {json.dumps({'type': 'start', 'query': q, 'canonical': canonical, 'query_meta': query_meta, 'stores': store_names}, ensure_ascii=False)}\n\n"

        _TIMEOUTS = {
            "Ozon": 38,
            "AMD.by": 20,
            "Wildberries": 20,
            "7745.by": 18,
        }
        DEFAULT_TIMEOUT = 14

        async def _search_with_timeout(scraper, query):
            name = getattr(scraper, "store_name", scraper.__class__.__name__)
            timeout = _TIMEOUTS.get(name, DEFAULT_TIMEOUT)
            try:
                return await asyncio.wait_for(scraper.search(query), timeout=timeout)
            except asyncio.TimeoutError:
                print(f"timeout {name} after {timeout}s — cancelling")
                return None
            except Exception as e:
                print(f"search error {name}: {e}")
                return None

        all_filtered: list = []
        debug: list[dict] = []

        async def run_round(query_str: str, qwords, filter_q: str):
            # хелпер фильтрации одного магазина
            def filter_one_store(raw: list, store_name: str):
                relevant = [p for p in raw if p.price > 0 and ScraperAggregator._is_relevant(p, qwords)]
                if not relevant:
                    return [], 0
                post_filtered = filter_products(filter_q, relevant)
                if not post_filtered:
                    return [], len(relevant)
                post_filtered.sort(key=lambda p: (ScraperAggregator._is_accessory(p), p.price))
                if store_name == tmp_agg._kufar.store_name:
                    final = post_filtered[:10]
                else:
                    final = [post_filtered[0]]
                return final, len(post_filtered)

            task_map: dict[asyncio.Task, object] = {}
            for scraper in scrapers_to_run:
                task_map[asyncio.create_task(_search_with_timeout(scraper, query_str))] = scraper
            pending = set(task_map.keys())
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    scraper = task_map[t]
                    store = getattr(scraper, "store_name", scraper.__class__.__name__)
                    try:
                        result = t.result()
                        if result is None:
                            debug.append({"store": store, "status": "error", "found": 0, "error": "таймаут"})
                            yield f"data: {json.dumps({'type': 'store', 'store': store, 'status': 'error', 'found': 0, 'error': 'таймаут', 'products': []}, ensure_ascii=False)}\n\n"
                            continue
                        if not isinstance(result, list):
                            debug.append({"store": store, "status": "empty", "found": 0})
                            yield f"data: {json.dumps({'type': 'store', 'store': store, 'status': 'empty', 'found': 0, 'products': []}, ensure_ascii=False)}\n\n"
                            continue
                        filtered, relevant_cnt = filter_one_store(result, store)
                        if filtered:
                            all_filtered.extend(filtered)
                            debug.append({"store": store, "status": "ok", "found": relevant_cnt})
                            prod_payload = [{"name": p.name, "price": p.price, "store": p.store, "url": p.url} for p in filtered]
                            yield f"data: {json.dumps({'type': 'store', 'store': store, 'status': 'ok', 'found': relevant_cnt, 'products': prod_payload}, ensure_ascii=False)}\n\n"
                        else:
                            debug.append({"store": store, "status": "empty", "found": 0})
                            yield f"data: {json.dumps({'type': 'store', 'store': store, 'status': 'empty', 'found': 0, 'products': [], 'relevant_raw': relevant_cnt if 'relevant_cnt' in locals() else 0}, ensure_ascii=False)}\n\n"
                    except asyncio.CancelledError:
                        debug.append({"store": store, "status": "error", "found": 0, "error": "cancelled"})
                        yield f"data: {json.dumps({'type': 'store', 'store': store, 'status': 'error', 'found': 0, 'error': 'cancelled', 'products': []}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        err = str(e)[:300]
                        debug.append({"store": store, "status": "error", "found": 0, "error": err})
                        yield f"data: {json.dumps({'type': 'store', 'store': store, 'status': 'error', 'found': 0, 'error': err, 'products': []}, ensure_ascii=False)}\n\n"

        # фаза 1 — original
        qwords_orig = ScraperAggregator._extract_query_words(q)
        async for ev in run_round(q, qwords_orig, q):
            yield ev
        # фаза 2 — canonical фолбэк если пусто и отличается
        if not all_filtered and canonical.strip().lower() != q.strip().lower():
            # сигнализируем фронту о фолбэке
            yield f"data: {json.dumps({'type': 'store', 'store': 'normalizer', 'status': 'ok', 'found': 0, 'products': [], 'note': f'fallback to canonical {canonical}'}, ensure_ascii=False)}\n\n"
            qwords_canon = ScraperAggregator._extract_query_words(canonical)
            async for ev in run_round(canonical, qwords_canon, canonical):
                yield ev

        # финальный done: сохраняем в БД и отдаём итоги
        all_filtered.sort(key=lambda p: p.price)
        # пометим is_best_price как в обычном search
        products_out = [{"id": 0, "name": p.name, "price": p.price, "store": p.store, "url": p.url, "is_best_price": (i == 0)} for i, p in enumerate(all_filtered[:30])]
        prices = [p.price for p in all_filtered]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        # сохраняем найденные товары
        if search_id is not None:
            try:
                async with async_session() as db2:
                    db_products = [Product(search_id=search_id, name=p.name, price=p.price, store=p.store, url=p.url) for p in all_filtered[:30]]
                    db2.add_all(db_products)
                    await db2.commit()
            except Exception:
                pass
        # закрываем браузеры
        try:
            await tmp_agg.close()
        except Exception:
            pass
        done_payload = {
            "type": "done",
            "total_results": len(all_filtered),
            "min_price": min_price,
            "max_price": max_price,
            "query_meta": query_meta,
            "debug": debug,
            "products": products_out,
        }
        yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "http://localhost:3000",
    })
