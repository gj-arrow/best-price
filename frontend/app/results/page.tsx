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

  const [searchQuery, setSearchQuery] = useState(query);
  const [isLoading, setIsLoading] = useState(false);
  const [products, setProducts] = useState<ProductCardProps[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'relevance' | 'price-asc' | 'price-desc'>('relevance');

  useEffect(() => {
    if (!query) {
      setProducts([]);
      setTotalResults(0);
      return;
    }

    setIsLoading(true);
    setError(null);

    fetch(`${API_URL}/api/search?q=${encodeURIComponent(query)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Ошибка ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setTotalResults(data.total_results || 0);
        const mapped: ProductCardProps[] = (data.products || []).map((p: ApiProduct) => ({
          name: p.name,
          price: p.price,
          storeName: p.store || 'Магазин',
          storeUrl: p.url || '#',
          isBestPrice: p.is_best_price,
          currency: 'BYN',
        }));
        setProducts(mapped);
      })
      .catch((err) => {
        setError(err.message);
        setProducts([]);
        setTotalResults(0);
      })
      .finally(() => setIsLoading(false));
  }, [query]);

  useEffect(() => {
    if (sortBy === 'relevance') return; // API returns by relevance already
    setProducts((prev) => {
      const sorted = [...prev];
      sorted.sort((a, b) =>
        sortBy === 'price-asc' ? a.price - b.price : b.price - a.price
      );
      return sorted;
    });
  }, [sortBy]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/results?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const priceRange =
    products.length > 0
      ? {
          min: Math.min(...products.map((p) => p.price)),
          max: Math.max(...products.map((p) => p.price)),
        }
      : { min: 0, max: 0 };

  const storeList = ['Onliner.by', 'Wildberries', 'Ozon', 'Shop.by', '1k.by', '360shop.by'];

  return (
    <div className="min-h-screen bg-[#f5f6fa] flex flex-col">
      {/* Header with search */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center gap-3">
            <a href="/" className="flex items-center gap-1.5 shrink-0">
              <div className="w-7 h-7 bg-violet-600 rounded-md flex items-center justify-center">
                <span className="text-white font-bold text-[11px]">B</span>
              </div>
              <span className="text-sm font-bold text-slate-800 hidden sm:inline">
                Best Price
              </span>
            </a>
            <form onSubmit={handleSearch} className="flex-1 flex gap-2">
              <div className="relative flex-1 max-w-lg">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
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
                  className="w-full pl-9 pr-3 py-2 bg-slate-100 rounded-lg text-sm text-slate-800 placeholder-slate-400 outline-none focus:bg-white focus:ring-2 focus:ring-violet-200 transition-all"
                />
              </div>
              <button
                type="submit"
                className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm rounded-lg transition-colors"
              >
                Найти
              </button>
            </form>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 max-w-6xl mx-auto px-4 py-5 w-full">
        {/* Results toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <div>
            <h1 className="text-lg font-bold text-slate-800">
              {query ? `«${query}»` : 'Все товары'}
            </h1>
            <p className="text-xs text-slate-500">
              {isLoading
                ? 'Поиск...'
                : error
                  ? 'Ошибка соединения'
                  : `Найдено ${totalResults} товаров`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {products.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs">
                <span className="text-slate-400">Цены:</span>
                <span className="font-semibold text-emerald-600">
                  {priceRange.min} BYN
                </span>
                <span className="text-slate-300">—</span>
                <span className="font-semibold text-red-500">{priceRange.max} BYN</span>
              </div>
            )}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-600 outline-none focus:ring-2 focus:ring-violet-200"
            >
              <option value="relevance">По релевантности</option>
              <option value="price-asc">Сначала дешёвые</option>
              <option value="price-desc">Сначала дорогие</option>
            </select>
          </div>
        </div>

        {/* Products grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {isLoading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <ProductCardSkeleton />
              </div>
            ))
          ) : error ? (
            <div className="col-span-full text-center py-12">
              <div className="w-12 h-12 mx-auto mb-3 bg-red-50 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="text-base font-semibold text-slate-600 mb-1">Ошибка соединения</h2>
              <p className="text-sm text-slate-400 mb-4">
                Не удалось подключиться к серверу. Убедитесь что бекенд запущен.
              </p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm rounded-lg transition-colors"
              >
                Повторить
              </button>
            </div>
          ) : products.length > 0 ? (
            products.map((product, i) => (
              <div
                key={`${product.name}-${i}`}
                className="animate-[fadeIn_0.3s_ease-out]"
                style={{ animationDelay: `${i * 50}ms`, animationFillMode: 'backwards' }}
              >
                <ProductCard {...product} />
              </div>
            ))
          ) : (
            /* Empty state */
            <div className="col-span-full text-center py-12">
              <div className="w-12 h-12 mx-auto mb-3 bg-slate-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h2 className="text-base font-semibold text-slate-600 mb-1">Ничего не найдено</h2>
              <p className="text-sm text-slate-400 mb-4">Попробуйте изменить запрос</p>
              <div className="text-[11px] text-slate-400 mb-4">
                Поиск осуществляется по: {storeList.join(', ')}
              </div>
              <button
                onClick={() => router.push('/')}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm rounded-lg transition-colors"
              >
                На главную
              </button>
            </div>
          )}
        </div>
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
