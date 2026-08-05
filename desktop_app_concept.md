# Koncepcja Aplikacji Desktopowej dla Zespołu QA (Cradle Automation)

Dokument zawiera analizę techniczną i architektoniczną stworzenia nowej aplikacji desktopowej dla członków zespołu QA automatyzacji Cradle.

---

## 💡 1. Cel i Rola Aplikacji Desktopowej

Obecny moduł `desktop-app/` działa jako skrypt konsolowy Python (`python src/main.py`), który serwuje serwer WebSocket (`:8765`) dla wtyczki Chrome.

Dla członków zespołu QA nowa Aplikacja Desktopowa z interfejsem graficznym (GUI) oraz ikony w zasobniku systemowym (System Tray / Menu Bar):
1. **Działa bez użycia konsoli**: Jednoklikowy instalator (`.dmg` dla macOS, `.exe` dla Windows).
2. **Pasek stanu (System Tray / Menu Bar)**: Dyskretna ikonka w zasobniku systemowym (zielona/żółta/czerwona kropka informująca o statusie połączenia z Cradle i serwerem NVC `:8001`).
3. **Automatyczne wykrywanie zasobów**: Monitoring podpięcia dysku sieciowego (np. `/Volumes/LucidLink` lub dysków mapowanych P:\).
4. **Powiadomienia systemowe (Toast Notifications)**: Natywne powiadomienia macOS/Windows o ukończonej analizie wideo, pobraniu assetu lub wymaganej weryfikacji (`REVIEW`).
5. **Skrót do panelu porównania**: Przycisk otwierający panel porównania w przeglądarce pod adresem `:8001`.

---

## 🔄 2. Architektura i Integracja z Wtyczką Chrome (`extension/`)

```
┌─────────────────────────────────────────┐
│     Przeglądarka Chrome / Webview       │
│   Strona Cradle: "My Team Tasks"        │
│    Rozszerzenie (cradle-scanner.js)     │
└────────────────────┬────────────────────┘
                     │ WebSocket (ws://localhost:8765)
                     ▼
┌─────────────────────────────────────────┐
│        Aplikacja Desktopowa Zespołu      │
│  - Serwer WebSocket (:8765)             │
│  - Pobieranie (Blob / Network / ZIP)    │
│  - Monitoring LucidLink / Dysk P:\      │
│  - Powiadomienia w zasobniku (Tray)     │
└────────────────────┬────────────────────┘
                     │ HTTP API (multipart upload / job trigger)
                     ▼
┌─────────────────────────────────────────┐
│      Główny Serwer NVC API (:8001)      │
│    Engine Porównania Wideo + AI Analyst │
└─────────────────────────────────────────┘
```

### Warianty Integracji Wtyczki:
- **Wariant 1: Hybrydowy (Rozszerzenie w Chrome + Aplikacja w Trayu)**:
  - Użytkownik pracuje w swojej przeglądarce Chrome, wtyczka skanuje Cradle i wysyła komendy WebSocket do aplikacji w zasobniku systemowym.
  - Aplikacja desktopowa w zasobniku pokazuje status połączenia (`Wtyczka połączona 🟢`), pobiera pliki lokalnie i wysyła do serwera NVC API (`:8001`).
- **Wariant 2: All-in-One (Wbudowane okno WebView z automatycznym wstrzykiwaniem wtyczki)**:
  - Jeden instalator aplikacji desktopowej z wbudowanym okienkiem przeglądarki i automatycznie wczytanym skryptem `cradle-scanner.js`.

---

## 🛠️ 3. Analiza Technologiczna

| Opcja | Stos Technologiczny | Rozmiar / Zużycie RAM | Zalety | Rekomendacja |
|---|---|---|---|---|
| **Opcja A** | **Tauri 2.0 + React + Python Sidecar** | ~15-20 MB / ~30 MB RAM | Ultra-lekka, nowoczesny interfejs React z brandbooka, natywny Tray | 🌟 **Najlepsza dla wydajności i UI** |
| **Opcja B** | **PySide6 / PyQt6 + PyInstaller** | ~80-110 MB / ~80 MB RAM | 100% kod w Pythonie, bezpośrednie użycie `desktop-app/src` | 👍 **Najprostsza realizacja w Pythonie** |
| **Opcja C** | **Electron + React** | ~120 MB / ~150 MB RAM | Łatwe prototypowanie webowe | ⚡ **Zwykły wybór webowy** |

---

## 📋 4. Plan Przyszłego Wdrożenia

1. **Etap 1**: Przygotowanie paczki instalatora dla `desktop-app` ze wsparciem System Tray (ikona w pasku zadań/menu bar).
2. **Etap 2**: Dodanie GUI ustawień (NVC Server URL, ścieżka do LucidLink, status WebSocket).
3. **Etap 3**: Dystrybucja pliku `.dmg` / `.exe` dla zespołu QA z automatycznym startem przy logowaniu.
