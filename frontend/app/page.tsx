'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';

const features = [
  { label: '6 магазинов', desc: 'Onliner.by, Wildberries, Ozon, Shop.by, 1k.by, 360shop.by' },
  { label: 'Реальные цены', desc: 'Обновляются каждые 5 минут' },
  { label: 'Экономия', desc: 'Находим лучшую цену за вас' },
];

export default function HomePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/results?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Simple header */}
      <header className="pt-4 px-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <a href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">B</span>
            </div>
            <span className="text-lg font-bold text-slate-800">Best Price</span>
          </a>
          <span className="text-xs text-slate-400">Поиск по 6 магазинам</span>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 -mt-12">
        <div className="w-full max-w-xl">
          {/* Headline */}
          <div className="text-center mb-8">
            <h1 className="text-3xl sm:text-4xl font-bold text-slate-800 tracking-tight">
              Сравните цены перед покупкой
            </h1>
            <p className="text-slate-500 mt-2 text-sm">
              Поиск по 6 магазинам — находите лучшие предложения
            </p>
          </div>

          {/* Search */}
          <form onSubmit={handleSubmit} className="mb-6">
            <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm hover:shadow-md hover:border-violet-200 focus-within:border-violet-400 focus-within:shadow-md focus-within:shadow-violet-100 transition-all duration-200">
              <svg className="w-5 h-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Введите название товара..."
                className="flex-1 bg-transparent text-slate-800 placeholder-slate-400 outline-none text-[15px]"
                autoFocus
              />
              <button
                type="submit"
                className="px-5 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm rounded-lg transition-colors whitespace-nowrap"
              >
                Найти
              </button>
            </div>
          </form>

          {/* Trust features */}
          <div className="grid grid-cols-3 gap-3">
            {features.map((f) => (
              <div key={f.label} className="text-center">
                <div className="text-xs font-semibold text-slate-700">{f.label}</div>
                <div className="text-[10px] text-slate-400 leading-tight mt-0.5">{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-3 px-4 border-t border-slate-100">
        <div className="max-w-3xl mx-auto text-center text-[11px] text-slate-400">
          Best Price © 2024 — Сравнение цен в реальном времени
        </div>
      </footer>
    </div>
  );
}
