'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

// Площадки для поиска — единый источник истины, синхронизирован с backend ScraperAggregator + results/page.tsx
const PLATFORMS = [
  'Onliner.by',
  'Wildberries',
  'Ozon',
  'Shop.by',
  '1k.by',
  '360shop.by',
  '21vek.by',
  '5element.by',
  'AMD.by',
  '7745.by',
] as const;

const features = [
  { label: `${PLATFORMS.length} площадок`, desc: PLATFORMS.slice(0, 6).join(', ') + ' и др.' },
  { label: 'Реальные цены', desc: 'Обновляются каждые 5 минут' },
  { label: 'Экономия', desc: 'Находим лучшую цену за вас' },
];

export default function HomePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [includeKufar, setIncludeKufar] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setIsSearching(true);
      const kufarParam = includeKufar ? '&include_kufar=true' : '';
      router.push(`/results?q=${encodeURIComponent(searchQuery.trim())}${kufarParam}`);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Simple header */}
      <header className="pt-3 sm:pt-4 px-3 sm:px-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-2">
          <a href="/" className="flex items-center gap-2 group shrink-0">
            <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">B</span>
            </div>
            <span className="text-[17px] sm:text-lg font-bold text-slate-800">Best Price</span>
          </a>
          <span className="text-[11px] sm:text-xs text-slate-400 whitespace-nowrap">Поиск по {PLATFORMS.length} площадкам</span>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-3 sm:px-4 py-6 sm:py-0 sm:-mt-12">
        <div className="w-full max-w-xl">
          {/* Headline */}
          <div className="text-center mb-6 sm:mb-8">
            <h1 className="text-[26px] leading-[1.15] sm:text-4xl font-bold text-slate-800 tracking-tight px-2 sm:px-0">
              Сравните цены перед покупкой
            </h1>
            <p className="text-slate-500 mt-2 text-[13px] sm:text-sm px-4 sm:px-0">
              Поиск по {PLATFORMS.length} площадкам — находите лучшие предложения
            </p>
          </div>

          {/* Search */}
          <form onSubmit={handleSubmit} className="mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 bg-white border border-slate-200 rounded-2xl sm:rounded-xl px-3 sm:px-4 py-3 sm:py-3 shadow-sm hover:shadow-md hover:border-violet-200 focus-within:border-violet-400 focus-within:shadow-md focus-within:shadow-violet-100 transition-all duration-200">
              <div className="flex items-center gap-2 flex-1 min-w-0 w-full">
                <svg className="w-5 h-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Введите название товара..."
                  className="flex-1 bg-transparent text-slate-800 placeholder-slate-400 outline-none text-base sm:text-[15px] min-w-0"
                  autoFocus
                  disabled={isSearching}
                  inputMode="search"
                  autoComplete="off"
                  enterKeyHint="search"
                />
              </div>
              <button
                type="submit"
                disabled={isSearching}
                className={`w-full sm:w-auto justify-center px-5 py-3 sm:py-2 text-white font-medium text-[15px] sm:text-sm rounded-xl sm:rounded-lg transition-colors whitespace-nowrap flex items-center gap-2 min-h-[44px] sm:min-h-0 ${
                  isSearching ? 'bg-violet-400 cursor-wait' : 'bg-violet-600 hover:bg-violet-700 active:bg-violet-800'
                }`}
              >
                {isSearching && (
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" aria-hidden />
                )}
                {isSearching ? 'Поиск...' : 'Найти'}
              </button>
            </div>
            {/* Прогресс поиска + Kufar toggle */}
            <div className="mt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-3">
              <button
                type="button"
                onClick={() => setIncludeKufar(!includeKufar)}
                title={includeKufar ? 'Kufar (б/у) включён — нажмите чтобы убрать' : 'Включить Kufar (б/у) в поиск'}
                className={`self-start sm:self-auto px-3 py-2 sm:py-1.5 rounded-lg text-xs font-medium border transition-colors whitespace-nowrap min-h-[36px] sm:min-h-0 ${
                  includeKufar
                    ? 'bg-amber-500 border-amber-500 text-white'
                    : 'bg-white border-slate-200 text-slate-500 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-700'
                }`}
              >
                Kufar (б/у)
              </button>
              {isSearching ? (
                <div className="flex items-center gap-2 text-xs text-violet-600" role="status" aria-live="polite">
                  <span className="w-3 h-3 border-2 border-violet-200 border-t-violet-600 rounded-full animate-spin" />
                  Идёт поиск по {PLATFORMS.length} площадкам…
                </div>
              ) : (
                <span className="text-[10px] sm:text-[11px] text-slate-400 leading-tight sm:truncate max-sm:line-clamp-2 max-sm:break-words">
                  <span className="sm:hidden">{PLATFORMS.slice(0, 5).join(' · ')} · …</span>
                  <span className="hidden sm:inline">{PLATFORMS.join(' · ')}</span>
                </span>
              )}
            </div>
            {isSearching && (
              <div className="mt-3 h-1 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-violet-600 rounded-full animate-pulse" style={{ width: '40%' }} />
              </div>
            )}
          </form>

          {/* Trust features */}
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            {features.map((f) => (
              <div key={f.label} className="text-center bg-white sm:bg-transparent border border-slate-100 sm:border-0 rounded-xl sm:rounded-none p-2.5 sm:p-0">
                <div className="text-[11px] sm:text-xs font-semibold text-slate-700">{f.label}</div>
                <div className="text-[10px] text-slate-400 leading-tight mt-1 sm:mt-0.5 line-clamp-2 sm:line-clamp-none">{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-3 px-3 sm:px-4 border-t border-slate-100">
        <div className="max-w-3xl mx-auto text-center text-[11px] text-slate-400">
          Best Price © 2024 — Сравнение цен в реальном времени
        </div>
      </footer>
    </div>
  );
}
