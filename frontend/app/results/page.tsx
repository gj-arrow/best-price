'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { ProductCard, type ProductCardProps } from '../../components/ProductCard';
import { ProductCardSkeleton } from '../../components/Skeleton';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiProduct {
  id: number;
  name: string;
  price: number;
  store: string | null;
  url: string | null;
  is_best_price: boolean;
}

function ResultsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.get('q') || '';
  const noCorrect = searchParams.get('no_correct') === '1';

  const [searchQuery, setSearchQuery] = useState(query);
  const [isLoading, setIsLoading] = useState(() => !!query);
  const [products, setProducts] = useState<ProductCardProps[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'relevance' | 'price-asc' | 'price-desc'>('price-asc');
  // includeKufar — применённый (из URL), pendingKufar — выбранный в UI, применяется только по "Найти" — по умолчанию включено
  const [includeKufar, setIncludeKufar] = useState(() => searchParams.get('include_kufar') !== 'false');
  const [pendingKufar, setPendingKufar] = useState(() => searchParams.get('include_kufar') !== 'false');
  const [queryMeta, setQueryMeta] = useState<null | { original: string; canonical: string; corrected: boolean; confidence: number; category: string }>(null);
  const [searchTick, setSearchTick] = useState(0);
  const [debug, setDebug] = useState<null | Array<{ store: string; status: string; found: number; error?: string }>>(null);
  const [liveStores, setLiveStores] = useState<Record<string, { status: string; found: number; error?: string }>>({});
  const [rubRate, setRubRate] = useState<number>(0.035617); // актуальный NBRB 2026-08-30, обновляется с /api/rate
  const abortRef = React.useRef<AbortController | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/rate`).then(r=>r.json()).then(d=>{ if(d?.rub_to_byn) setRubRate(d.rub_to_byn); }).catch(()=>{});
  }, []);

  // если все площадки уже ответили (12/12), не ждём done — считаем поиск завершённым сразу, без спиннера на 100%
  useEffect(() => {
    if (!isLoading) return;
    const entries = Object.entries(liveStores);
    if (!entries.length) return;
    const done = entries.filter(([, s]) => s.status !== 'searching').length;
    if (done === entries.length && done > 0) {
      const t = setTimeout(() => setIsLoading(false), 600);
      return () => clearTimeout(t);
    }
  }, [liveStores, isLoading]);

  const doSearch = React.useCallback((q: string, kufar: boolean, noCorr: boolean) => {
    if (!q) {
      setProducts([]);
      setTotalResults(0);
      setLiveStores({});
      return;
    }
    // отменяем предыдущий стрим
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setIsLoading(true);
    setError(null);
    setProducts([]);
    setTotalResults(0);
    setDebug(null);
    setLiveStores({});
    setQueryMeta(null);
    const kufarParam = `&include_kufar=${kufar ? 'true' : 'false'}`;
    const noCorrectParam = noCorr ? '&no_correct=1' : '';
    const url = `${API_URL}/api/search/stream?q=${encodeURIComponent(q)}${kufarParam}${noCorrectParam}`;
    // стрим SSE через fetch
    fetch(url, { signal: ctrl.signal, headers: { Accept: 'text/event-stream' } })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Ошибка ${res.status}`);
        if (!res.body) throw new Error('Нет потока');
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';
        const handleEvent = (evt: any) => {
          if (evt.type === 'start') {
            setQueryMeta(evt.query_meta || null);
            const stores: string[] = evt.stores || [];
            const init: Record<string, { status: string; found: number }> = {};
            stores.forEach((s: string) => (init[s] = { status: 'searching', found: 0 }));
            setLiveStores(init);
          } else if (evt.type === 'store') {
            const store: string = evt.store;
            const status: string = evt.status;
            setLiveStores((prev) => ({ ...prev, [store]: { status, found: evt.found || 0, error: evt.error } }));
            if (evt.products && evt.products.length) {
              const mapped: ProductCardProps[] = evt.products.map((p: any) => ({
                name: p.name,
                price: p.price,
                storeName: p.store || store,
                storeUrl: p.url || '#',
                isBestPrice: false, // пересчитаем в done/на лету
                currency: 'BYN' as const,
              }));
              setProducts((prev) => {
                const next = [...prev, ...mapped];
                // держим сортировку по цене для isBestPrice пересчёта позже, но показываем по мере прихода
                return next;
              });
              setTotalResults((prev) => prev + evt.products.length);
            }
          } else if (evt.type === 'done') {
            setQueryMeta(evt.query_meta || null);
            setTotalResults(evt.total_results || 0);
            setDebug(evt.debug || null);
            // финальный список — уже весь собрали инкрементально, но синхронизируем цены/бэйджи
            if (evt.products) {
              const mapped: ProductCardProps[] = evt.products.map((p: any) => ({
                name: p.name,
                price: p.price,
                storeName: p.store || 'Магазин',
                storeUrl: p.url || '#',
                isBestPrice: p.is_best_price,
                currency: 'BYN' as const,
              }));
              setProducts(mapped);
            }
            // liveStores финальный из debug если есть
            if (evt.debug) {
              const fin: Record<string, { status: string; found: number; error?: string }> = {};
              evt.debug.forEach((d: any) => (fin[d.store] = { status: d.status, found: d.found, error: d.error }));
              setLiveStores(fin);
            }
            setIsLoading(false);
          }
        };
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf('\n\n')) !== -1) {
            const chunk = buf.slice(0, idx).trim();
            buf = buf.slice(idx + 2);
            if (!chunk) continue;
            const lines = chunk.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const evt = JSON.parse(line.slice(6));
                  handleEvent(evt);
                } catch {}
              }
            }
          }
        }
        setIsLoading(false);
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return;
        setError(err.message || 'Ошибка соединения');
        setProducts([]);
        setTotalResults(0);
        setDebug(null);
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    doSearch(query, includeKufar, noCorrect);
  }, [query, includeKufar, noCorrect, searchTick, doSearch]);

  // синхронизируем pending с URL когда URL меняется извне — по умолчанию Куфар включён (missing => true)
  useEffect(() => { setPendingKufar(includeKufar); }, [includeKufar]);
  useEffect(() => { setIncludeKufar(searchParams.get('include_kufar') !== 'false'); }, [searchParams]);
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  // сортировка теперь на уровне отображения (через useMemo ниже), чтобы live-результаты тоже были отсортированы
  // state products остаётся в порядке прихода, сортируется только при рендере

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    const kufarParam = `&include_kufar=${pendingKufar ? 'true' : 'false'}`;
    const target = `/results?q=${encodeURIComponent(q)}${kufarParam}`;
    const same =
      q === query && pendingKufar === includeKufar && !noCorrect;
    if (same) {
      setSearchTick((t) => t + 1);
      router.replace(target);
    } else {
      // применяем pendingKufar
      setIncludeKufar(pendingKufar);
      router.push(target);
    }
  };

  const formatPrice = (value: number): string =>
    Number.isInteger(value) ? String(Math.round(value)) : value.toFixed(1);

  const baseStores = ['Onliner.by', 'Wildberries', 'Ozon', 'Shop.by', '1k.by', '360shop.by', '21vek.by', '5element.by', 'AMD.by', '7745.by'];
  const storeList = includeKufar ? [...baseStores, 'Kufar.by (б/у)'] : baseStores;

  // Разделяем: новые магазины / Kufar б/у / Google AI оценка РФ
  const googleAiProduct = products.find((p) => p.storeName?.includes('Google AI'));
  const kufarProducts = products.filter((p) => p.storeName?.toLowerCase().includes('kufar'));
  const regularProductsRaw = products.filter((p) => !p.storeName?.includes('Google AI') && !p.storeName?.toLowerCase().includes('kufar'));
  const regularProducts = React.useMemo(() => {
    if (sortBy === 'price-asc') return [...regularProductsRaw].sort((a, b) => a.price - b.price);
    if (sortBy === 'price-desc') return [...regularProductsRaw].sort((a, b) => b.price - a.price);
    return regularProductsRaw;
  }, [regularProductsRaw, sortBy]);

  const priceRange =
    regularProducts.length > 0
      ? {
          min: Math.min(...regularProducts.map((p) => p.price)),
          max: Math.max(...regularProducts.map((p) => p.price)),
        }
      : { min: 0, max: 0 };

  const kufarSorted = [...kufarProducts].sort((a, b) => a.price - b.price);
  const kufarTop3 = kufarSorted.slice(0, 3);
  const kufarStats =
    kufarProducts.length > 0
      ? {
          min: Math.min(...kufarProducts.map((p) => p.price)),
          max: Math.max(...kufarProducts.map((p) => p.price)),
          avg: Math.round(kufarProducts.reduce((s, p) => s + p.price, 0) / kufarProducts.length),
          count: kufarProducts.length,
        }
      : null;

  // дебаг live: пока идёт стрим — из liveStores, после done — из debug (финальный)
  const debugRows: Array<{ store: string; status: string; found: number; error?: string }> | null =
    debug ?? (Object.keys(liveStores).length ? Object.entries(liveStores).map(([store, st]) => ({ store, status: st.status, found: st.found, error: st.error })) : null);

  return (
    <div className="min-h-screen bg-[#f5f6fa] flex flex-col">
      {/* Header with search */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200 supports-[backdrop-filter]:bg-white/70">
        <div className="max-w-6xl mx-auto px-3 sm:px-4 py-2 sm:py-3">
          <div className="flex items-center gap-2 sm:gap-3">
            <a href="/" className="flex items-center gap-1.5 shrink-0" aria-label="На главную">
              <div className="w-8 h-8 sm:w-7 sm:h-7 bg-violet-600 rounded-md flex items-center justify-center">
                <span className="text-white font-bold text-[11px]">B</span>
              </div>
              <span className="text-sm font-bold text-slate-800 hidden sm:inline">
                Best Price
              </span>
            </a>
            <form onSubmit={handleSearch} className="flex-1 flex gap-1.5 sm:gap-2 min-w-0">
              <div className="relative flex-1 max-w-lg min-w-0">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Поиск товаров..."
                  className="w-full pl-9 pr-3 py-2.5 sm:py-2 bg-slate-100 rounded-xl sm:rounded-lg text-base sm:text-sm text-slate-800 placeholder-slate-400 outline-none focus:bg-white focus:ring-2 focus:ring-violet-200 transition-all"
                  inputMode="search"
                  autoComplete="off"
                  enterKeyHint="search"
                />
              </div>
              <button
                type="submit"
                className="px-4 sm:px-4 py-2.5 sm:py-2 bg-violet-600 hover:bg-violet-700 active:bg-violet-800 text-white font-medium text-sm rounded-xl sm:rounded-lg transition-colors shrink-0 min-h-[44px] sm:min-h-0"
              >
                Найти
              </button>
            </form>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-5 w-full">
        {/* Красивый прогресс-блок */}
        {/* Live streaming поиск — по мере готовности магазинов */}
        {isLoading && (
          <div className="mb-4 bg-white border border-violet-100 rounded-2xl p-4 sm:p-5 shadow-sm">
            {(() => {
              const entries = Object.entries(liveStores);
              const total = entries.length || storeList.length;
              const done = entries.filter(([, s]) => s.status !== 'searching').length;
              const pct = total ? Math.round((done / total) * 100) : 6;
              const searching = entries.filter(([, s]) => s.status === 'searching').map(([k]) => k);
              const allDone = total > 0 && done === total;
              return (
                <>
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${allDone ? 'bg-emerald-500' : 'bg-violet-600'}`}>
                      {allDone ? (
                        <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                      ) : (
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-slate-800 flex items-center gap-2 flex-wrap">
                        {allDone ? 'Поиск завершён' : 'Ищем лучшие цены'}
                        {!allDone && (
                          <span className="inline-flex gap-1">
                            <span className="w-1 h-1 bg-violet-400 rounded-full animate-bounce [animation-delay:0ms]" />
                            <span className="w-1 h-1 bg-violet-400 rounded-full animate-bounce [animation-delay:150ms]" />
                            <span className="w-1 h-1 bg-violet-400 rounded-full animate-bounce [animation-delay:300ms]" />
                          </span>
                        )}
                        {allDone && <span className="inline-flex px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[11px]">готово</span>}
                        <span className="ml-auto text-xs font-normal text-slate-500">{done}/{total} площадок · найдено {totalResults}</span>
                      </div>
                      <div className="text-xs text-slate-500 truncate">
                        {allDone ? `Готово · все площадки ответили` : searching.length ? `Ищется сейчас: ${searching.join(' · ')}` : `Осталось ${total - done} — почти готово…`}
                        {queryMeta?.canonical && <span className="text-slate-400"> · {queryMeta.canonical}</span>}
                      </div>
                    </div>
                    <div className={`text-xs font-bold hidden sm:block ${allDone ? 'text-emerald-600' : 'text-violet-600'}`}>{pct}%</div>
                  </div>
                  <div className="mt-3 h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-500 ${allDone ? 'bg-emerald-500' : 'bg-gradient-to-r from-violet-600 to-indigo-500'}`} style={{ width: `${pct}%` }} />
                  </div>
                  {/* пилюли по магазинам — какая площадка на каком этапе */}
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {(entries.length ? entries : storeList.map((s) => [s, { status: 'searching', found: 0 }] as const)).map(([store, st]) => (
                      <span
                        key={store}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
                          st.status === 'searching'
                            ? 'bg-slate-50 border-slate-200 text-slate-500'
                            : st.status === 'ok'
                              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                              : st.status === 'empty'
                                ? 'bg-slate-50 border-slate-200 text-slate-400'
                                : 'bg-red-50 border-red-200 text-red-600'
                        }`}
                        title={st.error || ''}
                      >
                        {st.status === 'searching' && <span className="w-3 h-3 border-2 border-slate-300 border-t-violet-600 rounded-full animate-spin" />}
                        {st.status === 'ok' && <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />}
                        {st.status === 'empty' && <span className="w-1.5 h-1.5 bg-slate-300 rounded-full" />}
                        {st.status === 'error' && <span className="w-1.5 h-1.5 bg-red-500 rounded-full" />}
                        {store}
                        {st.status !== 'searching' && <span className="opacity-60">{st.found ? `· ${st.found}` : st.status === 'ok' ? '· 1' : ''}</span>}
                      </span>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                    <span>Результаты появляются по мере готовности — не жди окончания</span>
                    <span className="hidden sm:inline">{pct}% · {totalResults} товаров уже найдено</span>
                  </div>
                </>
              );
            })()}
          </div>
        )}
        {/* Results toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 sm:mb-5">
          <div className="min-w-0">
            <h1 className="text-[17px] sm:text-lg font-bold text-slate-800 truncate">
              {query ? `«${query}»` : 'Все товары'}
            </h1>
            {queryMeta?.corrected && (
              <div aria-live="polite" className="mt-1 text-xs flex flex-wrap items-center gap-1.5">
                <span className="text-slate-500">Показаны результаты для</span>
                <span className="font-semibold text-slate-800">&quot;{queryMeta.canonical}&quot;</span>
                <span className="text-slate-400">·</span>
                <a
                  href={`/results?q=${encodeURIComponent(queryMeta.original)}&no_correct=1${includeKufar ? '&include_kufar=true' : ''}`}
                  onClick={(e) => {
                    e.preventDefault();
                    router.push(`/results?q=${encodeURIComponent(queryMeta.original)}&no_correct=1${includeKufar ? '&include_kufar=true' : ''}`);
                  }}
                  className="text-violet-600 hover:underline"
                >
                  Искать &quot;{queryMeta.original}&quot;
                </a>
              </div>
            )}
            <p className="text-xs text-slate-500">
              {isLoading
                ? 'Поиск...'
                : error
                  ? 'Ошибка соединения'
                  : `Найдено ${totalResults} товаров`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {regularProducts.length > 0 && (
              <div className="flex items-center gap-2 px-2.5 sm:px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs whitespace-nowrap">
                <span className="text-slate-400 hidden xs:inline">Цены:</span>
                <span className="font-semibold text-emerald-600">
                  {formatPrice(priceRange.min)} BYN
                </span>
                <span className="text-slate-300">—</span>
                <span className="font-semibold text-red-500">{formatPrice(priceRange.max)} BYN</span>
              </div>
            )}
            <button
              type="button"
              onClick={() => setPendingKufar((v) => !v)}
              aria-pressed={pendingKufar}
              title={pendingKufar ? 'Kufar (б/у) выбран — нажми Найти чтобы применить' : 'Добавить Kufar (б/у), применится по Найти'}
              className={`px-3 py-2 sm:py-1.5 rounded-xl sm:rounded-lg text-xs sm:text-sm font-medium border transition-colors whitespace-nowrap min-h-[36px] sm:min-h-0 flex-1 sm:flex-none justify-center ${
                pendingKufar
                  ? 'bg-amber-500 border-amber-500 text-white hover:bg-amber-600'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700'
              }`}
            >
              + Куфар б\у
            </button>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="flex-1 sm:flex-none min-w-[140px] px-3 py-2 sm:py-1.5 bg-white border border-slate-200 rounded-xl sm:rounded-lg text-xs sm:text-sm text-slate-600 outline-none focus:ring-2 focus:ring-violet-200 min-h-[36px] sm:min-h-0"
            >
              <option value="relevance">По релевантности</option>
              <option value="price-asc">Сначала дешёвые</option>
              <option value="price-desc">Сначала дорогие</option>
            </select>
          </div>
        </div>

        {/* Новые товары — показываем по мере прихода, даже пока isLoading */}
        {error ? (
          <div className="text-center py-12 bg-white border border-slate-200 rounded-2xl">
            <div className="w-12 h-12 mx-auto mb-3 bg-red-50 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-base font-semibold text-slate-600 mb-1">Ошибка соединения</h2>
            <p className="text-sm text-slate-400 mb-4">Не удалось подключиться к серверу. Убедитесь что бекенд запущен.</p>
            <button onClick={() => window.location.reload()} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm rounded-lg transition-colors">
              Повторить
            </button>
          </div>
        ) : regularProducts.length > 0 ? (
          <div className="bg-white border border-emerald-200 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-4 sm:px-5 py-3 bg-gradient-to-r from-emerald-50 to-teal-50 border-b border-emerald-100 flex flex-wrap items-center gap-3">
              <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" /></svg>
              </div>
              <div className="min-w-0">
                <div className="text-sm font-bold text-slate-800 flex flex-wrap items-center gap-2">
                  Новые товары — с площадок
                  <span className="px-2 py-0.5 bg-emerald-500 text-white text-[10px] font-bold rounded-full">{regularProducts.length} найдено</span>
                </div>
                <div className="text-xs text-slate-500">Onliner, WB, Ozon, Shop.by и др. · новые, с гарантией</div>
              </div>
              <div className="ml-auto flex items-center gap-2 text-xs">
                <span className="hidden sm:inline px-2.5 py-1 bg-white border border-emerald-200 rounded-full">
                  средн. <b className="text-emerald-700">{formatPrice(Math.round(regularProducts.reduce((s,p)=>s+p.price,0)/regularProducts.length))} BYN</b>
                </span>
                <span className="px-2.5 py-1 bg-white border border-emerald-200 rounded-full">
                  {formatPrice(priceRange.min)} — {formatPrice(priceRange.max)} BYN
                </span>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-3 sm:p-4 items-stretch">
              {regularProducts.map((product, i) => {
                const isCheapest = product.price === priceRange.min;
                return (
                  <div
                    key={`${product.name}-${i}`}
                    className={`animate-[fadeIn_0.3s_ease-out] rounded-xl overflow-hidden border-2 transition-all flex flex-col h-full ${isCheapest ? 'bg-emerald-50 border-emerald-400 shadow-md' : 'border-transparent bg-white'}`}
                    style={{ animationDelay: `${i * 50}ms`, animationFillMode: 'backwards' }}
                  >
                    {isCheapest && <div className="px-3 py-1 bg-emerald-500 text-white text-[10px] font-bold text-center tracking-wide shrink-0">ЛУЧШАЯ ЦЕНА</div>}
                    <ProductCard {...product} className="flex-1" />
                  </div>
                );
              })}
            </div>
            <div className="px-4 pb-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
              <span>Мин: <b className="text-emerald-700">{formatPrice(priceRange.min)} BYN</b></span><span>·</span>
              <span>Средн: <b className="text-slate-700">{formatPrice(Math.round(regularProducts.reduce((s,p)=>s+p.price,0)/regularProducts.length))} BYN</b></span><span>·</span>
              <span>Макс: <b className="text-slate-700">{formatPrice(priceRange.max)} BYN</b></span>
              <span className="text-slate-400">· зелёным — лучшая цена среди новых</span>
            </div>
          </div>
        ) : isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <ProductCardSkeleton />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 bg-white border border-slate-200 rounded-2xl">
            <div className="w-12 h-12 mx-auto mb-3 bg-slate-100 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h2 className="text-base font-semibold text-slate-600 mb-1">Ничего не найдено</h2>
            <p className="text-sm text-slate-400 mb-4">Попробуйте изменить запрос</p>
            <div className="text-[11px] text-slate-400 mb-4">Поиск по: {storeList.join(', ')}</div>
            <button onClick={() => router.push('/')} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm rounded-lg transition-colors">
              На главную
            </button>
          </div>
        )}

        {/* Куфар б\у — показываем по мере прихода, даже пока идёт стрим */}
        {includeKufar && !error && kufarProducts.length > 0 && (
          <div className="mt-4">
            <div className="bg-white border border-amber-200 rounded-2xl overflow-hidden shadow-sm">
              <div className="px-4 sm:px-5 py-3 bg-gradient-to-r from-amber-50 to-orange-50 border-b border-amber-100 flex flex-wrap items-center gap-3">
                <div className="w-8 h-8 bg-amber-500 rounded-lg flex items-center justify-center shrink-0">
                  <span className="text-white text-[11px] font-bold">K</span>
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-bold text-slate-800 flex flex-wrap items-center gap-2">
                    Куфар · б/у — для ориентира
                    <span className="px-2 py-0.5 bg-amber-500 text-white text-[10px] font-bold rounded-full">топ 3</span>
                  </div>
                  <div className="text-xs text-slate-500">Объявления с Kufar.by · б/у и новые</div>
                </div>
                {kufarStats && (
                  <div className="ml-auto flex items-center gap-2 text-xs">
                    <span className="hidden sm:inline px-2.5 py-1 bg-white border border-amber-200 rounded-full">
                      средн. <b className="text-amber-700">{formatPrice(kufarStats.avg)} BYN</b>
                    </span>
                    <span className="px-2.5 py-1 bg-white border border-amber-200 rounded-full">
                      {formatPrice(kufarStats.min)} — {formatPrice(kufarStats.max)} BYN
                    </span>
                    <span className="hidden xs:inline text-slate-400">{kufarStats.count} объ.</span>
                  </div>
                )}
              </div>

              {kufarTop3.length > 0 ? (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 sm:p-4">
                    {kufarTop3.map((p, i) => (
                      <a
                        key={`kufar-${i}`}
                        href={p.storeUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group border border-slate-200 rounded-xl p-3 hover:border-amber-300 hover:shadow-md transition-all bg-slate-50/50 hover:bg-white flex flex-col gap-2"
                      >
                        <div className="text-xs font-medium text-slate-800 line-clamp-2 leading-tight group-hover:text-amber-700">
                          {p.name}
                        </div>
                        <div className="mt-auto flex items-center justify-between">
                          <span className="text-[11px] px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">Kufar.by</span>
                          <span className="text-sm font-bold text-slate-800">{formatPrice(p.price)} BYN</span>
                        </div>
                      </a>
                    ))}
                  </div>
                  {kufarStats && kufarStats.count > 3 && (
                    <div className="px-4 pb-3 text-center">
                      <a
                        href={`https://www.kufar.by/l/r~minsk?query=${encodeURIComponent(query)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-amber-600 hover:underline"
                      >
                        ещё {kufarStats.count - 3} объявлений на Куфаре →
                      </a>
                    </div>
                  )}
                  {kufarStats && (
                    <div className="px-4 pb-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
                      <span>Мин: <b className="text-slate-700">{formatPrice(kufarStats.min)} BYN</b></span>
                      <span>·</span>
                      <span>Средн: <b className="text-amber-700">{formatPrice(kufarStats.avg)} BYN</b></span>
                      <span>·</span>
                      <span>Макс: <b className="text-slate-700">{formatPrice(kufarStats.max)} BYN</b></span>
                      <span className="text-slate-400">· для ориентира (б/у цены ниже новых)</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="p-6 text-center text-sm text-slate-400">На Куфаре ничего не найдено по запросу «{query}»</div>
              )}
            </div>
          </div>
        )}

        {/* Google AI (РФ) — примерная цена, выше дебага — показываем сразу как приходит (live) */}
        {googleAiProduct && !error && (
          <div className="mt-4 mx-3 sm:mx-0 p-3 sm:p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0">
                <span className="text-white text-[10px] font-bold">AI</span>
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-slate-800 flex flex-wrap items-center gap-1.5">
                  Примерная цена в РФ
                  <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[10px] font-bold rounded">Google AI</span>
                  <span className="text-[10px] text-slate-400 font-normal">оценка</span>
                </div>
                <div className="text-xs text-slate-500">
                  По данным Google AI Mode •{' '}
                  <a href={googleAiProduct.storeUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    проверить в Google
                  </a>
                </div>
              </div>
            </div>
            <div className="text-left sm:text-right shrink-0">
              <div className="text-lg font-bold text-blue-700">{formatPrice(googleAiProduct.price)} BYN</div>
              <div className="text-xs text-slate-500">~{Math.round(googleAiProduct.price / rubRate).toLocaleString('ru-RU')} ₽ · курс {rubRate.toFixed(4)}</div>
            </div>
          </div>
        )}

        {/* Дебаг: поиск по всем площадкам — live во время стрима, финал после done — теперь ниже Google AI */}
        {debugRows && (
          <div className="mt-6 bg-white border border-slate-200 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-amber-400 animate-pulse' : 'bg-slate-400'}`} />
              <h3 className="text-xs font-bold text-slate-700 tracking-wide uppercase">Дебаг · поиск по площадкам {isLoading ? '· live' : ''}</h3>
              <span className="ml-auto text-[11px] text-slate-400">{debugRows.filter(d=>d.status==='ok').length} нашли · {debugRows.filter(d=>d.status==='empty').length} пусто · {debugRows.filter(d=>d.status==='error').length} ошибка · {debugRows.filter(d=>d.status==='searching').length} ищутся</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Магазин</th>
                    <th className="text-left px-3 py-2 font-medium">Статус</th>
                    <th className="text-left px-3 py-2 font-medium">Нашлось</th>
                    <th className="text-left px-3 py-2 font-medium hidden sm:table-cell">Детали</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {debugRows.map((d) => (
                    <tr key={d.store} className={d.status==='error' ? 'bg-red-50/50' : d.status==='ok' ? 'bg-emerald-50/30' : d.status==='searching' ? 'bg-amber-50/30' : ''}>
                      <td className="px-3 py-2 font-medium text-slate-800 whitespace-nowrap">{d.store}</td>
                      <td className="px-3 py-2">
                        {d.status==='ok' && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[11px] font-bold">● нашёл</span>}
                        {d.status==='empty' && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[11px]">— нет товара</span>}
                        {d.status==='error' && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-[11px] font-bold">✕ {d.error === 'таймаут' ? 'таймаут' : 'ошибка'}</span>}
                        {d.status==='searching' && <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[11px]"><span className="w-2 h-2 border border-amber-400 border-t-amber-700 rounded-full animate-spin" /> ищется</span>}
                      </td>
                      <td className="px-3 py-2 text-slate-600">{d.status==='searching' ? '—' : d.found}</td>
                      <td className="px-3 py-2 text-slate-400 hidden sm:table-cell max-w-[280px] truncate" title={d.error || ''}>{d.error || (d.status==='empty' ? 'поиск сработал, релевантных нет' : d.status==='ok' ? 'поиск сработал' : d.status==='searching' ? 'в процессе…' : '')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-2 bg-slate-50 text-[11px] text-slate-400">Поиск идёт во все площадки параллельно · live из стрима {isLoading ? '· обновляется' : '· финал'} · Куфар {includeKufar ? 'включён' : 'выключен'} · таймаут {isLoading ? 'до 26с' : 'сработал'}</div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-3 bg-white/50">
        <div className="max-w-6xl mx-auto px-4 text-center text-[11px] text-slate-400">
          Best Price © 2024 · Сравнение цен в реальном времени
        </div>
      </footer>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#f5f6fa] flex items-center justify-center">
          <div className="text-center">
            <div className="w-8 h-8 border-[3px] border-violet-200 border-t-violet-600 rounded-full animate-spin mx-auto mb-3"></div>
            <p className="text-sm text-slate-500">Загрузка...</p>
          </div>
        </div>
      }
    >
      <ResultsContent />
    </Suspense>
  );
}
