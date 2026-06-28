# Frontend Google Dark Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign PriceSearch main page in Google-minimalist style with Dark Neon color scheme and framer-motion animations

**Architecture:** 7 sequential tasks — config → global styles → layout → main page → results page → component CSS → skeleton colors. Each task builds on previous, all touch only frontend files.

**Tech Stack:** Next.js 14, React 18, Tailwind CSS 3.4, Framer Motion 11

## Global Constraints

- All new colors must be added to `tailwind.config.js` before use in components
- framer-motion v11.x is already installed — do not install additional animation libraries
- Existing component logic (ProductCard, PriceBlock, Skeleton) must remain unchanged — only CSS module colors and utility classes may be updated
- Main page uses `'use client'` — animations require client component
- Results page uses `Suspense` wrapper — keep this pattern

---

### Task 1: Tailwind Config — Neon Colors + Glow Animations

**Files:**
- Modify: `frontend/tailwind.config.js` — add colors, extend animation keyframes

**Interfaces:**
- Consumes: nothing
- Produces: `tailwind.config.js` with new `colors.neon`, `colors.glass`, extended `keyframes` and `animation`

- [ ] **Step 1: Add neon and glass color tokens**

Replace the `colors` section in `theme.extend` with expanded palette:

```js
colors: {
  primary: { /* keep existing */ },
  secondary: { /* keep existing */ },
  accent: { /* keep existing */ },
  neon: {
    purple: '#a855f7',
    cyan: '#06b6d4',
    pink: '#ec4899',
    blue: '#3b82f6',
  },
  glass: {
    white: 'rgba(255, 255, 255, 0.04)',
    light: 'rgba(255, 255, 255, 0.06)',
    medium: 'rgba(255, 255, 255, 0.08)',
    border: 'rgba(255, 255, 255, 0.10)',
    hover: 'rgba(255, 255, 255, 0.12)',
  },
  dark: {
    bg: '#0a0a1a',
    bgEnd: '#1a0a2e',
    surface: '#111128',
    card: '#0f0f2a',
    text: '#f1f5f9',
    muted: '#94a3b8',
    dim: '#64748b',
  },
}
```

- [ ] **Step 2: Add glow keyframes and animations**

Add to `keyframes` inside `theme.extend`:

```js
keyframes: {
  // ... keep existing keyframes
  glow: {
    '0%, 100%': {
      boxShadow: '0 0 20px rgba(168, 85, 247, 0.15), 0 0 40px rgba(6, 182, 212, 0.1)',
      borderColor: 'rgba(168, 85, 247, 0.3)',
    },
    '50%': {
      boxShadow: '0 0 30px rgba(168, 85, 247, 0.3), 0 0 60px rgba(6, 182, 212, 0.2)',
      borderColor: 'rgba(168, 85, 247, 0.5)',
    },
  },
  'glow-subtle': {
    '0%, 100%': { opacity: '0.3' },
    '50%': { opacity: '0.6' },
  },
  shimmer: {
    '0%': { backgroundPosition: '-200% 0' },
    '100%': { backgroundPosition: '200% 0' },
  },
}
```

Add to `animation` inside `theme.extend`:

```js
animation: {
  // ... keep existing animations
  'glow': 'glow 3s ease-in-out infinite',
  'glow-subtle': 'glow-subtle 2s ease-in-out infinite',
  'shimmer': 'shimmer 3s linear infinite',
}
```

---

### Task 2: Globals CSS — Dark Theme CSS Variables

**Files:**
- Modify: `frontend/styles/globals.css` — update CSS variables for dark theme

- [ ] **Step 1: Replace root CSS variables with dark neon theme**

Replace `@layer base { :root { ... } }` block:

```css
@layer base {
  :root {
    --background: 240 27% 7%;        /* #0a0a1a */
    --foreground: 210 40% 98%;        /* #f1f5f9 */
    --card: 240 20% 10%;              /* #111128 */
    --card-foreground: 210 40% 98%;
    --popover: 240 20% 10%;
    --popover-foreground: 210 40% 98%;
    --primary: 271 91% 65%;           /* #a855f7 */
    --primary-foreground: 210 40% 98%;
    --secondary: 215 25% 27%;         /* #334155 */
    --secondary-foreground: 210 40% 98%;
    --muted: 215 16% 47%;             /* #64748b */
    --muted-foreground: 215 20% 65%;
    --accent: 271 91% 65%;            /* #a855f7 */
    --accent-foreground: 210 40% 98%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 210 40% 98%;
    --border: 240 10% 15%;            /* #262640 approx */
    --input: 240 10% 15%;
    --ring: 271 91% 65%;              /* #a855f7 */
    --radius: 0.75rem;
  }
}
```

Remove the `.dark` class block (we are always dark now).

- [ ] **Step 2: Add bg-gradient utility to body**

Update the `body` rule:

```css
body {
  @apply bg-gradient-to-br from-[#0a0a1a] via-[#0f0a2a] to-[#1a0a2e] text-foreground;
  font-feature-settings: "rlig" 1, "calt" 1;
}
```

---

### Task 3: Layout — Metadata + Body Classes

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Update metadata for Russian-language price search app**

```tsx
export const metadata: Metadata = {
  title: 'PriceSearch — Сравнение цен в реальном времени',
  description: 'Ищите товары и сравнивайте цены из 6 магазинов. Быстрый поиск цен на Onliner, Re:Store, М.Видео и другие.',
  keywords: ['PriceSearch', 'сравнение цен', 'поиск товаров', 'цены', 'онлайн-покупки'],
  authors: [{ name: 'PriceSearch Team' }],
  creator: 'PriceSearch Team',
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'PriceSearch',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'PriceSearch — Сравнение цен',
    description: 'Ищите товары и сравнивайте цены из 6 магазинов.',
  },
  viewport: {
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
  },
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#0a0a1a' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0a1a' },
  ],
};
```

- [ ] **Step 2: Update html and body classes**

```tsx
<html lang="ru" className={`${inter.variable}`} suppressHydrationWarning>
  <body className="font-sans antialiased min-h-screen text-foreground">
    {children}
  </body>
</html>
```

Remove `bg-background` from body (we set gradient in globals.css).

---

### Task 4: Main Page — Google Dark Redesign with Animations

**Files:**
- Modify: `frontend/app/page.tsx` — complete rewrite with framer-motion

- [ ] **Step 1: Write the complete redesigned page**

Full content:

```tsx
'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';

export default function HomePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/results?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  const quickCategories = [
    { name: 'iPhone', icon: '📱' },
    { name: 'MacBook', icon: '💻' },
    { name: 'AirPods', icon: '🎧' },
    { name: 'Apple Watch', icon: '⌚' },
  ];

  const features = [
    { icon: '⚡', title: 'Быстро', desc: 'Поиск за 0.5 сек' },
    { icon: '🎯', title: 'Точно', desc: '6 магазинов сразу' },
    { icon: '💰', title: 'Выгодно', desc: 'Лучшие цены' },
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.3 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
  };

  const featureVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Animated background gradient orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10">
        <div className="absolute -top-40 -right-40 w-[500px] h-[500px] rounded-full bg-purple-500/10 blur-[120px] animate-glow-subtle" />
        <div className="absolute -bottom-40 -left-40 w-[400px] h-[400px] rounded-full bg-cyan-500/10 blur-[100px] animate-glow-subtle" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-indigo-500/5 blur-[150px]" />
      </div>

      {/* Main Content */}
      <main className="flex-1 flex flex-col items-center justify-center px-4">
        <motion.div
          className="w-full max-w-xl"
          initial="hidden"
          animate="visible"
          variants={containerVariants}
        >
          {/* Logo — Google-style big centered */}
          <motion.div variants={itemVariants} className="text-center mb-10">
            <div className="inline-flex items-center justify-center gap-4 mb-2">
              <div className="relative">
                <div className="w-14 h-14 bg-gradient-to-br from-purple-500 via-fuchsia-500 to-cyan-400 rounded-2xl flex items-center justify-center shadow-2xl shadow-purple-500/30">
                  <span className="text-white font-extrabold text-xl">P</span>
                </div>
                <div className="absolute -inset-1 bg-gradient-to-br from-purple-500/20 to-cyan-400/20 rounded-2xl blur-xl -z-10" />
              </div>
            </div>
            <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight">
              <span className="bg-gradient-to-r from-purple-400 via-fuchsia-300 to-cyan-300 bg-clip-text text-transparent">
                PriceSearch
              </span>
            </h1>
            <p className="text-slate-500 mt-3 text-sm">
              Сравнивайте цены в реальном времени
            </p>
          </motion.div>

          {/* Search Bar — Google-style with neon glow */}
          <motion.div variants={itemVariants} className="mb-10">
            <form onSubmit={handleSubmit}>
              <div
                className={`
                  flex items-center bg-white/[0.06] backdrop-blur-xl
                  rounded-2xl border overflow-hidden
                  transition-all duration-500 ease-out
                  ${isFocused
                    ? 'border-purple-500/40 shadow-[0_0_30px_rgba(168,85,247,0.15),0_0_60px_rgba(6,182,212,0.1)]'
                    : 'border-white/[0.08] shadow-lg shadow-black/20'
                  }
                `}
              >
                <div className="pl-5 flex items-center text-slate-500">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Что ищем? Например: iPhone 16..."
                  className="flex-1 px-4 py-4 bg-transparent text-slate-100 placeholder-slate-600 outline-none text-base"
                  autoFocus
                />
                <motion.button
                  type="submit"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="m-2 px-6 py-2.5 bg-gradient-to-r from-purple-500 to-cyan-500 text-white font-semibold rounded-xl hover:from-purple-600 hover:to-cyan-600 transition-all shadow-lg shadow-purple-500/20"
                >
                  Найти
                </motion.button>
              </div>
            </form>
          </motion.div>

          {/* Quick Categories — 2x2 grid glassmorphism */}
          <motion.div variants={itemVariants} className="mb-8">
            <div className="grid grid-cols-2 gap-3">
              {quickCategories.map((cat, i) => (
                <motion.button
                  key={cat.name}
                  onClick={() => router.push(`/results?q=${cat.name}`)}
                  whileHover={{ y: -4, scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="group p-4 bg-white/[0.04] backdrop-blur-md rounded-2xl border border-white/[0.08] hover:border-purple-500/30 hover:bg-white/[0.08] transition-all duration-300"
                  variants={itemVariants}
                >
                  <div className="w-10 h-10 mx-auto mb-2 rounded-xl bg-gradient-to-br from-white/10 to-white/5 flex items-center justify-center text-xl group-hover:scale-110 transition-transform">
                    {cat.icon}
                  </div>
                  <span className="text-sm font-semibold text-slate-300 group-hover:text-slate-100 transition-colors">
                    {cat.name}
                  </span>
                </motion.button>
              ))}
            </div>
          </motion.div>

          {/* Features — subtle bottom row */}
          <motion.div
            variants={itemVariants}
            className="grid grid-cols-3 gap-3"
          >
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                variants={featureVariants}
                className="text-center p-3 bg-white/[0.02] rounded-xl border border-white/[0.05]"
              >
                <div className="text-lg mb-0.5">{f.icon}</div>
                <div className="text-xs font-semibold text-slate-400">{f.title}</div>
                <div className="text-[10px] text-slate-600">{f.desc}</div>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </main>

      {/* Footer */}
      <motion.footer
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2, duration: 0.5 }}
        className="flex-shrink-0 border-t border-white/[0.06] py-4"
      >
        <div className="max-w-4xl mx-auto px-4 text-center text-xs text-slate-600">
          PriceSearch &copy; 2024 &middot; Поиск по 6 магазинам
        </div>
      </motion.footer>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file builds**

```bash
cd frontend && npx next build --no-lint 2>&1 | tail -20
```
Expected: No errors (type errors may appear for framer-motion types if @types missing — acceptable for runtime)

---

### Task 5: Results Page — Consistent Dark Theme

**Files:**
- Modify: `frontend/app/results/page.tsx`

- [ ] **Step 1: Rewrite ResultsContent with dark theme**

Replace entire `ResultsContent` return block. Key changes:
- Outer container: `min-h-screen flex flex-col bg-transparent` (inherits body gradient)
- Header: `bg-black/30 backdrop-blur-xl border-b border-white/[0.06]`
- Logo text: gradient purple→cyan instead of blue→cyan
- Search input: `bg-white/[0.06] text-slate-100 placeholder-slate-600`
- Sort select: `bg-white/[0.06] text-slate-300 border-white/[0.08]`
- Price range box: `bg-white/[0.04] border-white/[0.08]`
- Product grid cards: update borders/backgrounds to dark theme in the JSX wrappers (the actual `ProductCard` component keeps its own .module.css colors — we fix those in Task 6)
- Results heading: `text-slate-100`
- No results state: `bg-white/[0.04] border-white/[0.08] text-slate-300`
- Footer: `border-white/[0.06] text-slate-600`
- Loading spinner: purple border instead of blue

Add `'use client'` at top and `motion` import.

- [ ] **Step 2: Add staggered fade-in animation for product cards**

Wrap the products grid with `motion.div` using `containerVariants`/`itemVariants` similar to main page:

```tsx
// Inside the products.map section, wrap each product card
{products.map((product, i) => (
  <motion.div
    key={`${product.name}-${i}`}
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: i * 0.05, duration: 0.4, ease: 'easeOut' }}
    className="bg-white/[0.04] backdrop-blur-md rounded-xl border border-white/[0.08] overflow-hidden hover:border-purple-500/30 hover:bg-white/[0.06] transition-all duration-300"
  >
    <ProductCard {...product} />
  </motion.div>
))}
```

---

### Task 6: ProductCard CSS — Dark Theme Colors

**Files:**
- Modify: `frontend/components/ProductCard.module.css`

- [ ] **Step 1: Update card background and border colors for dark theme**

Replace color values in `.card`:
- `background: #ffffff` → `background: rgba(255, 255, 255, 0.04)`
- `border: 1px solid #e2e8f0` → `border: 1px solid rgba(255, 255, 255, 0.08)`
- `.card:hover` `border-color: #3b82f6` → `border-color: rgba(168, 85, 247, 0.5)`
- `.card:hover` `box-shadow` → `0 20px 40px rgba(0, 0, 0, 0.3)`
- `.card.bestPrice` `border: 2px solid #10b981` → keep green, it's an accent
- `.imageWrapper` background: `#f8fafc` → `rgba(255, 255, 255, 0.04)`, `#e2e8f0` → `rgba(255, 255, 255, 0.08)`
- `.name` `color: #1e293b` → `color: #f1f5f9`
- `.description` `color: #64748b` → `color: #94a3b8`
- `.price` `color: #1e293b` → `color: #f1f5f9`
- `.originalPrice` `color: #94a3b8` → `color: #64748b`
- `.storeRow` `border-bottom: 1px solid #f1f5f9` → `border-bottom: 1px solid rgba(255, 255, 255, 0.06)`
- `.storeName` `color: #64748b` → `color: #94a3b8`
- `.storeName::before` keep green dot
- `.buyButton` gradient: `#3b82f6/#2563eb` → `#a855f7/#7e22ce` (purple to match neon theme)
- `.buyButton` `box-shadow` → update to purple shadow

- [ ] **Step 2: Add subtle border glow on hover for bestPrice cards**

`.card.bestPrice:hover`:
```css
.card.bestPrice:hover {
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3), 0 0 20px rgba(16, 185, 129, 0.15);
}
```

---

### Task 7: Skeleton Colors — Dark Theme

**Files:**
- Modify: `frontend/components/Skeleton.tsx`

- [ ] **Step 1: Update skeleton background color**

Change the skeleton div class:
```tsx
// before
className={`bg-slate-200 animate-pulse ${className}`}
// after
className={`bg-white/[0.06] animate-pulse ${className}`}
```

---

### Task 8: Verification

- [ ] **Step 1: Build the frontend**

```bash
cd frontend && npx next build 2>&1 | tail -30
```

Expected: successful build with no errors

- [ ] **Step 2: Start dev server and visually verify**

```bash
cd frontend && npx next dev
```

Open http://localhost:3000 — verify:
- Dark gradient background visible
- Logo with purple-cyan gradient text
- Search bar with glow on focus
- Category cards with glassmorphism
- Animations play on load
- Navigation to `/results?q=iPhone` works
- Results page has dark theme
- Product cards display with dark theme colors
