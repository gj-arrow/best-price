# Frontend Google Dark Redesign

## Overview
Redesign the PriceSearch frontend main page in Google-like minimalistic style with Dark Neon color scheme and framer-motion animations.

## Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `bg-primary` | `#0a0a1a` | Base background |
| `bg-secondary` | `#1a0a2e` | Gradient end |
| `card-bg` | `rgba(255,255,255,0.04)` | Category/feature cards |
| `card-border` | `rgba(255,255,255,0.08)` | Card borders |
| `search-bg` | `rgba(255,255,255,0.06)` | Search input background |
| `glow-primary` | `#a855f7` | Purple neon (logo, focus) |
| `glow-secondary` | `#06b6d4` | Cyan neon (gradient partner) |
| `text-primary` | `#f1f5f9` | Main text |
| `text-secondary` | `#94a3b8` | Secondary text |
| `text-muted` | `#64748b` | Muted text |

## Layout (Main Page)

```
┌──────────────────────────────────────┐
│  [логотип PriceSearch]               │
│         (большой, по центру)         │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ 🔍 Поиск товаров...    [Найти] │  │ ← neon glow on focus
│  └────────────────────────────────┘  │
│                                      │
│  ┌──────┐  ┌──────┐                │
│  │ 📱   │  │ 💻   │                │ ← glassmorphism cards
│  │ iPhone│  │MacBook│               │    staggered animation
│  └──────┘  └──────┘                │
│  ┌──────┐  ┌──────┐                │
│  │ 🎧   │  │ ⌚   │                │
│  │AirPods│  │A.Watch│               │
│  └──────┘  └──────┘                │
│                                      │
│  ⚡ Быстро  🎯 Точно  💰 Выгодно    │ ← small, muted
│                                      │
│  PriceSearch © 2024 · Поиск ...     │ ← footer
└──────────────────────────────────────┘
```

## Animations (framer-motion)

| Element | Animation | Delay | Duration |
|---------|-----------|-------|----------|
| Logo | `fadeIn` + `scaleIn` | 0s | 0.6s |
| Search bar | `fadeInUp` | 0.2s | 0.5s |
| Categories (each) | `fadeInUp` | stagger 0.1s (start 0.4s) | 0.4s |
| Features (each) | `fadeIn` | stagger 0.08s (start 0.8s) | 0.3s |

### Interactive animations
- **Search focus**: border animates to purple-cyan gradient glow + box-shadow glow
- **Card hover**: `y: -4px`, box-shadow glow increase, border becomes translucent
- **Button hover**: gradient shift, shadow intensity increase

## Scope
- **Main page** (`page.tsx`) — full redesign
- **Layout** (`layout.tsx`) — update metadata (title, description in Russian), body bg class
- **Tailwind config** (`tailwind.config.js`) — new colors, extend with neon animations
- **Globals** (`globals.css`) — update root CSS variables for dark theme
- **Results page** (`results/page.tsx`) — consistent dark theme (read existing first)

## Files to modify
1. `frontend/tailwind.config.js` — add neon colors, glow keyframes
2. `frontend/styles/globals.css` — dark theme CSS variables
3. `frontend/app/layout.tsx` — metadata, body classes
4. `frontend/app/page.tsx` — main Google-like page with animations
5. `frontend/app/results/page.tsx` — consistent dark styling

## Out of scope
- Components (`PriceBlock`, `ProductCard`, `Skeleton`) — keep as-is, only ensure dark theme compat
- Backend changes
- Functional logic changes
