# BRAIN.md — Mózg Projektu

## O projekcie

**Cradle Video Automation** to system automatyzacji procesu QA wideo dla agencji EGPlus Warsaw. System porównuje pliki akceptacyjne (acceptance) z emisyjnymi (emission) i identyfikuje różnice wizualne, dźwiękowe i czasowe.

### Architektura

```
Browser Extension (Chrome)
    ↕ WebSocket :8765
Desktop App (Python)
    ↕ REST API :8001
New Video Compare (FastAPI + React)
    ↕ SQLite
Dashboard + Stats
```

### Komponenty

| Komponent | Technologia | Lokalizacja |
|---|---|---|
| Extension | JavaScript (vanilla) | `extension/` |
| Desktop App | Python 3.9, asyncio | `desktop-app/` |
| Backend NVC | FastAPI, SQLAlchemy, FFmpeg | `new_video_compare/backend/` |
| Frontend NVC | React, TypeScript, Vite | `new_video_compare/frontend/` |

---

## Workflow Cradle

### Kroki w tabeli komentarzy (od najnowszego)

| # | Krok | Co zawiera | Rola |
|---|---|---|---|
| 1 | **QA Final Proofreading** | Komentarz końcowy | Ostatni check |
| 2 | **Final/Broadcast File Preparation** | Plik emisji (attachment lub network path) | **EMISSION** |
| 3 | **QA Proofreading** | "ok" (zatwierdzenie) | Potwierdzenie |
| 4 | **Video Preparation** | Plik akceptu (attachment) | **ACCEPTANCE** |
| 5+ | Wcześniejsze wersje | Starsze pliki | Ignorowane |

### Reguły identyfikacji plików

**Acceptance (akcept):**
1. Priorytet: `video preparation` → `file preparation` → `qa proofreading`
2. Pierwszy trafiony wiersz = najnowsza wersja (tabela sortowana od najnowszego)
3. Tylko pliki `.mp4`, `.mov`, `.mxf`, `.zip`
4. Ignoruj `.png`, `.jpg`, `.pdf` (screenshoty klienta, nie pliki wideo)

**Emission (emis):**
1. Szukaj w wierszach `final file preparation` lub `broadcast file preparation`
2. Typ `attachment` → pobierz z URL Cradle
3. Typ `network_path` → kopiuj z dysku sieciowego `/Volumes/egpluswarsaw/...`
4. Ścieżka sieciowa: regex `\/Volumes\/[^\n\r"'` + `<>]+`, trim trailing apostrophes

### Klienci

Nazwa klienta parsowana z nazwy pliku/projektu:

| Klient | Przykład w nazwie | Uwagi |
|---|---|---|
| Electrolux | `AEG_Localization`, `Electrolux` | Wymagający, dużo assetów |
| Philips | `Philips.ArtworkMaster` | Inny format kroków workflow |
| MG | `MG-SPRING-SALE` | Krótkie spoty (6s) |
| Spoticar | `SPOTICAR`, `Spoticar` | TV spoty |

---

## Zasady kodowania

### Python (Backend / Desktop App)
- **Python 3.9+**, async/await gdzie możliwe
- **SQLAlchemy ORM** — nigdy surowy SQL
- **Pathlib** — nigdy `os.path.join()`
- **Logging** — `logger.info/warning/error` z emoji statusu
- **Type hints** — na parametrach funkcji i return values
- Komentuj tylko skomplikowane funkcje, nie oczywisty kod
- Zmienne i funkcje: `snake_case`
- Klasy: `PascalCase`

### JavaScript (Extension)
- **Vanilla JS** — bez frameworków (to content script)
- **Async/await** — nigdy raw `.then()` chains
- **Console.log** z tagiem `[CradleScanner]` i emoji
- Sprawdzaj `chrome.runtime` przed użyciem (może być undefined)
- Fallback: zawsze miej plan B (blob download, WebSocket move)

### React/TypeScript (Frontend NVC)
- **Vite** — dev server na `:3000`
- **TypeScript** — strict mode
- Komponenty: functional + hooks
- State management: React hooks (useState, useEffect)
- API calls: Axios przez `api.ts`

### CSS
- Vanilla CSS z custom properties
- Dark mode jako domyślny
- Glassmorphism, gradients, micro-animations
- Mobile responsive

---

## Styl pracy

### Commits
Format: `type: description`
- `fix:` — naprawa buga
- `feat:` — nowa funkcjonalność
- `refactor:` — zmiana bez zmiany zachowania
- `docs:` — dokumentacja

### Testowanie
- Zawsze testuj na żywych przypadkach z Cradle
- Minimum 3 różne case'y przed merge
- Sprawdź edge-case'y: puste tabele, brak plików, I/O error na network path

### Debugging
- Extension: `console.log` + Chrome DevTools
- Desktop App: `desktop-app/logs/process.log`
- NVC Backend: stdout + `new_video_compare.db`

---

## Aktualny cel

### Faza bieżąca
- ✅ Naprawienie pobierania plików (Extension + Desktop App)
- ✅ Filtrowanie rozszerzeń (tylko wideo)
- ✅ Fix identyfikacji acceptance (video preparation)
- ⬜ Refaktor Desktop App → API Client (usunięcie Playwright)

### Następne kroki
- ⬜ E2E flow: Extension → Desktop App → NVC API
- ⬜ Polling loop w Extension (autonomia Agenta 1)
- ⬜ Modele DB: `CradleAsset`, `AnalysisResult`
- ⬜ `analyst_service.py` z integracją LLM
- ⬜ Stats Dashboard widget
- ⬜ Retention Service (auto-cleanup plików)

### Długoterminowo
- ⬜ Agent 3: Self-Correction
- ⬜ Migracja SQLite → PostgreSQL (gdy potrzebna)
- ⬜ Multi-agent orchestration

---

## Ważne ścieżki

| Co | Ścieżka |
|---|---|
| Extension content script | `extension/content/cradle-scanner.js` |
| Extension background | `extension/background/background.js` |
| Desktop App server | `desktop-app/src/websocket_server.py` |
| Desktop App file handler | `desktop-app/src/file_handler.py` |
| NVC Backend entry | `new_video_compare/backend/main.py` |
| NVC Models | `new_video_compare/backend/models/models.py` |
| NVC Config | `new_video_compare/backend/config.py` |
| NVC Frontend App | `new_video_compare/frontend/src/App.tsx` |
| NVC Dashboard | `new_video_compare/frontend/src/components/Dashboard.tsx` |
| Downloads folder | `~/Downloads/{cradleId}/` |
| Network drive | `/Volumes/egpluswarsaw/alfa/Electrolux/TV/...` |

---

## Znane pułapki

1. **`chrome.runtime` = undefined** — W content script po pewnym czasie Chrome "wygasza" runtime. Zawsze sprawdzaj dostępność i miej fallback.
2. **Trailing apostrophe w ścieżkach** — Komentarze Cradle zawierają ścieżki typu `...broadcast'`. Regex musi wykluczać `'` `"` `` ` ``.
3. **ZIP w nazwie .mp4** — Niektóre emisje to `plik.mp4.zip`. Po rozpakowaniu szukaj największego pliku wideo.
4. **I/O Error na network path** — Dyski sieciowe bywają niestabilne. Zawsze retry + graceful fallback.
5. **PNG jako acceptance** — Klienci wrzucają screenshoty z uwagami. Filtruj po rozszerzeniu!
6. **Stara wersja pliku** — Tabela ma wiele wierszy. Zawsze bierz PIERWSZY trafiony (= najnowszy).
7. **CSP violations** — Strona Cradle blokuje iframes. To normalne, ignoruj te errory.
