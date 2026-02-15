# AGENTS.md — System 3 Agentów

## Przegląd

System składa się z 3 autonomicznych agentów, które współpracują w celu pełnej automatyzacji procesu QA wideo w Cradle. Każdy agent ma jasno zdefiniowaną rolę, odpowiedzialność i granice działania.

---

## Agent 1: Controller — "Ręce" 🤖

**Nazwa kodowa:** `Controller`
**Komponenty:** Browser Extension (`cradle-scanner.js`) + Desktop App (`websocket_server.py`, `file_handler.py`)

### Odpowiedzialność
- Monitoring strony Cradle "My Team Tasks" co ~2 minuty
- Filtrowanie assetów po kroku "QA Final Proofreading"
- Branie assetów (z obsługą "asset taken by someone else")
- Identyfikacja plików acceptance i emission z tabeli komentarzy
- Pobieranie plików (blob download, network paths, ZIP extraction)
- Przenoszenie plików do folderów `{cradleId}/`
- Tworzenie jobów porównania w NVC API

### Zachowanie
- **Autonomiczny:** Działa w pętli bez interwencji użytkownika
- **Odporny:** Automatyczny reconnect WebSocket, retry przy pobieraniu
- **Selektywny:** Pobiera tylko pliki wideo (`.mp4`, `.mov`, `.mxf`, `.zip`)
- **Chronologiczny:** Zawsze wybiera najnowszą wersję acceptance i emission

### Komunikacja
| Kierunek | Kanał | Format |
|---|---|---|
| Extension → Desktop App | WebSocket `:8765` | JSON actions |
| Desktop App → Extension | WebSocket `:8765` | JSON responses |
| Desktop App → NVC | HTTP API `:8001` | REST + multipart |

### Metryki sukcesu
- % assetów prawidłowo pobranych
- Czas od wzięcia assetu do uruchomienia porównania
- Ilość błędów pobierania / dzień

---

## Agent 2: Analyst — "Mózg" 🧠

**Nazwa kodowa:** `Analyst`
**Komponenty:** `analyst_service.py`, modele `CradleAsset` + `AnalysisResult`

### Odpowiedzialność
- Monitoring ukończonych jobów porównania (status = `COMPLETED`)
- Analiza wyników porównania (różnice frame, audio, timecodes)
- Podejmowanie decyzji: **APPROVE** / **REJECT** / **REVIEW**
- Generowanie uzasadnienia decyzji (reasoning)
- Postowanie komentarzy z werdyktem na Cradle
- Gromadzenie historii decyzji do nauki

### Zachowanie
- **Analityczny:** Ocena oparta na danych, nie intuicji
- **Ostrożny:** W razie wątpliwości → `REVIEW` (wymaga interwencji człowieka)
- **Uczący się:** Buduje bazę wiedzy z historii decyzji per klient
- **Transparentny:** Zawsze podaje uzasadnienie decyzji

### Reguły decyzyjne
| Sytuacja | Werdykt |
|---|---|
| Brak różnic lub tylko kosmetyczne | ✅ APPROVE |
| Różnice w treści, brakujące klatki, desync audio | ❌ REJECT |
| Granica / niejednoznaczne / nowy typ różnicy | 👤 REVIEW |
| Confidence score < 0.7 | 👤 REVIEW |

### Komunikacja
| Kierunek | Kanał | Format |
|---|---|---|
| NVC → Analyst | Wewnętrzny trigger / polling | Python |
| Analyst → DB | SQLAlchemy | ORM |
| Analyst → LLM | HTTP API | OpenAI / Google AI |
| Analyst → Cradle | HTTP POST | Cradle API |

### Metryki sukcesu
- Accuracy werdyktów (vs. decyzje ludzkiego QA)
- % assetów wymagających REVIEW (im mniej, tym lepiej)
- Średni czas analizy
- Koszt tokenów LLM / dzień

---

## Agent 3: Developer — "Inżynier" 🔧

**Nazwa kodowa:** `Developer`
**Komponenty:** Planowany — przyszła implementacja
**Status:** Konceptualny

### Odpowiedzialność
- Monitoring logów systemu i wskaźników błędów
- Identyfikacja wzorców false-positive i false-negative
- Sugerowanie zmian progów czułości NVC
- Alert gdy reject rate przekroczy próg (>30% / dzień)
- Auto-tuning parametrów na podstawie historii

### Zachowanie
- **Obserwujący:** Ciągle monitoruje metryki systemu
- **Proaktywny:** Sugeruje zmiany zanim problem eskaluje
- **Konserwatywny:** Nigdy nie zmienia parametrów bez potwierdzenia
- **Raportujący:** Generuje raporty tygodniowe

---

## Interakcje między agentami

```
Controller ──(pliki)──→ NVC ──(wyniki)──→ Analyst
                                              │
                                              ├──→ Cradle (komentarz)
                                              ├──→ DB (historia)
                                              └──→ Dashboard (statystyki)
                                                        │
Developer ←──(metryki)──────────────────────────────────┘
    │
    └──→ Sugestie tuning (do potwierdzenia przez człowieka)
```

## Zasada nadrzędna

> **Żaden agent nie podejmuje nieodwracalnej akcji bez potwierdzenia człowieka.**
> Controller może pobierać pliki autonomicznie, ale Analyst przy wątpliwościach zawsze eskaluje do REVIEW. Developer nigdy nie zmienia kodu samodzielnie.
