# Smart Search: Нормализация запроса + фильтрация категории (айфон → iPhone, без чехлов)

**Дата:** 2026-08-30  
**Статус:** Draft → Approved (секции 1-4 аппрувнуты)  
**Автор:** brainstorming с пользователем  
**Связано:** `backend/scrapers/aggregator.py` (`_is_relevant`, `_is_accessory`), `backend/scrapers/*`, `frontend/app/page.tsx`, `frontend/app/results/page.tsx`

## 1. Контекст и проблема

Сейчас `GET /api/search?q` уходит напрямую в 10 скреперов. `aggregator._is_relevant` требует strong-модель токены, `_is_accessory` отбрасывает чехлы по первым 3 токенам. На запросе `айфон 15 про макс 256` (кириллица + пробелы) токены не совпадают с `iPhone 15 Pro Max 256GB` → 0 релевантных. Опечатки `аифон 15 пра макс` тоже не ловятся. Аксессуары `Чехол для iPhone 15 Pro Max` проскакивают, если нет маркера в первых токенах.

Цель: понимать запрос как Google — транслит, опечатки, категория — и искать по каноникалу, отметая ненужные категории.

**Требования пользователя (уточнены):**
- UX: Оба — авто-исправление `айфон → iPhone` + бейдж "Показаны результаты для X · Искать айфон …" с `&no_correct=1`.
- Фильтр: B — `Категория + модель` — `iPhone 15 Pro Max` любой объём = релевантно, `iPhone 15` без `Pro Max` и любые чехлы/стёкла/зарядки = отсев.
- Технология: C — Баланс: локально 80% запросов бесплатно/офлайн, фолбэк в LLM/Google только при низкой уверенности.

## 2. Архитектура и поток данных

```
User: "айфон 15 пра макс 256" (original)
  → Frontend GET /api/search?q=айфон 15 пра макс 256
  → Backend QueryNormalizer.normalize(q) [параллельно с прогревом браузеров]
      → { canonical:"iPhone 15 Pro Max 256GB", confidence:0.92, must_tokens:[iphone,15,pro,max], category:"smartphone", storage:"256", corrected:true }
  → ScraperAggregator.search_all(canonical)  // 10 скреперов, не original
  → PostFilter(canonical, category)
      → must_tokens ALL required + category_score>0.72 + !is_accessory → sorted (is_accessory в хвост)
  → Response { products, query:{original, canonical, corrected, confidence}, total_results }
  → Frontend бейдж + grid
  → При клике "Искать айфон …" → GET ?q=original&no_correct=1 → normalize skip
```

Кэш: `query_normalizations(original PK → canonical, confidence, category, hits, updated_at)` TTL 30д. Инвалидация при пополнении словаря.

Флаг отката: `NORMALIZER_ENABLED` в `.env`, `?no_correct=1` на запрос.

## 3. Компоненты (изолированные)

### 3.1 `backend/normalizer/translit.py`
Словарь 300 брендов/терминов: `айфон→iphone, самсунг→samsung, телик→tv, пылесос→vacuum`, `ё→е`, `про→pro`, `макс→max`. Чистая функция, без I/O, 0.1мс. Покрывает кириллицу → латиницу.

### 3.2 `backend/normalizer/fuzzy_dict.py`
Каноникал-словарь 500-800 моделей: из `SELECT DISTINCT` товаров + ручной список топ-100 (`iphone 15 pro max`, `xiaomi tv a pro 55`). `rapidfuzz` Levenshtein ≤2, `confidence = fuzz.ratio /100`. Возвращает `canonical` если `confidence>0.85`. Покрывает опечатки `пра→pro` (dist 1), `ксиоми→xiaomi` (dist 2). Латентность <20мс.

### 3.3 `backend/normalizer/llm_normalizer.py`
Промпт для `gpt-4o-mini` (или локальной tiny): `SYSTEM: normalize query to {canonical, category, must_tokens}` — `USER: айфон 15 пра макс 25б`. Валидация: `canonical` должен содержать ≥1 токен из словаря, иначе отброс. Timeout 800мс, стоимость ~$0.0003. Вызывается только при `fuzzy confidence <0.85`.

### 3.4 `backend/normalizer/query_normalizer.py`
Оркестратор: `translit → fuzzy → if conf<0.85 → llm_normalizer/google_ai → cache.get/set → return`. Параллелится с прогревом Playwright, не добавляет латентность к `search_all` (3-8с).

### 3.5 `backend/filter/post_filter.py`
Замена `_is_relevant` + `_is_accessory`:
- `must_tokens` ALL required (как сейчас для strong ID, но теперь для canonical).
- `category_score` — эмбеддинг `canonical` vs `product.name` (all-MiniLM-L6-v2 локально или `text-embedding-3-small`), threshold 0.72. Отметает `iPhone 15` когда нужен `Pro Max`.
- `is_accessory` — эвристика + `llm_classifier` tiny (50мс) для спорных: `is_case_for_iphone?`. Сортировка `score = must_match*0.6 + category*0.4 - is_accessory*1.0`, threshold 0.85 для B (строго скрыть).

### 3.6 `DB: query_normalizations`
Миграция Alembic:
```sql
CREATE TABLE query_normalizations (
  original TEXT PRIMARY KEY,
  canonical TEXT NOT NULL,
  confidence REAL NOT NULL,
  category TEXT,
  hits INT DEFAULT 1,
  updated_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_canonical ON query_normalizations(canonical);
```

### 3.7 `Frontend`
- `app/page.tsx` — подсказка при вводе (опц. `canonical` preview), отправка `q` как есть.
- `app/results/page.tsx` — бейдж коррекции `Показаны результаты для "iPhone 15 Pro Max 256GB" · Искать "айфон …"`, `aria-live`, `&no_correct=1` toggle. Бейдж цены/фильтры без изменений, но `storeList` уже 10 площадок.

## 4. Обработка ошибок и фолбэки

| Сценарий | Поведение |
|----------|-----------|
| LLM/Google timeout 800мс | Используем `fuzzy` результат, логируем `fallback_timeout`, не блокируем скреперы |
| `canonical` → 0 результатов, `original` → >0 | Ретрай `search_all(original)` в фоне, показываем original-результаты + бейдж "Ничего по исправленному, показаны по original" |
| LLM галлюцинация (`canonical` вне словаря, conf<0.7) | Отбрасываем, берём `fuzzy` |
| Спорная категория (score 0.6-0.85) | De-prioritize внизу, не скрываем полностью; при B строго threshold 0.85 скрыть |
| Кэш промах + словарь пополнился | Инвалидация: при `INSERT` новой модели `DELETE` кэш где `canonical` содержит старую модель |
| `NORMALIZER_ENABLED=false` или `?no_correct=1` | Пропуск нормализатора, прямой `search_all(original)` |

Производительность: `normalize` <20мс (локально) / <900мс (фолбэк), идёт параллельно с браузерами → +0мс к итоговому `search_all`.

## 5. Тестирование и метрики

**Юнит (pytest):**
- `translit`: 30 кейсов `айфон→iphone`, `ёж→ezh`
- `fuzzy`: `айфон 15 пра макс→iphone 15 pro max` (dist1), `ксиоми тв 55→xiaomi tv 55` (0.88)
- `post_filter`: `iPhone 15 Pro Max 256GB` vs `Чехол для iPhone 15 Pro Max` → `accessory=True`; vs `iPhone 15 128GB` → `must_fail`; vs `iPhone 15 Pro Max 512GB` → `pass`

**Интеграционные (Playwright + API):**
- `q=айфон 15 про макс` → `canonical contains pro max` + `category smartphone` + топ-10 без чехлов
- `q=аифон 15 пра макс 256` (2 опечатки) → `confidence>0.85` + `canonical 256GB`
- `q=xiaomi tv 55` (латиница) → без коррекции, но `category tv`

**Метрики (логи/DB):** `correction_rate`, `fallback_rate`, `filter_precision`, `zero_results_canonical`, `cache_hit_rate`. Дашборд в `GET /api/stats/normalizer`.

**Rollout:** feature flag `NORMALIZER_ENABLED`, `hits` для приоритета, `TTL 30д`, ручная очистка `DELETE FROM query_normalizations`.

## 6. Вне скоупа (YAGNI)

- Полный семантический поиск по описанию товара (только `name`).
- Персональные рекомендации.
- Автодополнение в инпуте (отдельный спек).
- Локализация на EN (только RU/BY).

## 7. Открытые вопросы (закрыты)

- UX Both — решено: бейдж + `no_correct`.
- Фильтр B — решено: must_tokens + category.
- Баланс — решено: локально → фолбэк.

## 8. Следующий шаг

Инвок `writing-plans` → план реализации с задачами, оценкой, порядком (normalizer → filter → frontend → тесты).
