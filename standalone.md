# Architektura Standalone (Local Desktop App)

Ten dokument opisuje wzorzec projektowy użyty do przekształcenia webowej aplikacji React + FastAPI w lokalną, samodzielną aplikację pulpitową dla systemu macOS (`.app`). Wzorzec ten można łatwo replikować dla innych narzędzi.

## Główne założenia

Aplikacja standalone składa się z trzech ściśle zintegrowanych warstw:
1. **Skompilowany Frontend (React):** Zbudowana wersja statyczna (HTML, JS, CSS) serwowana lokalnie bez potrzeby uruchamiania serwera Node.js.
2. **Lekki Backend (FastAPI):** Pythonowy serwer uruchamiany lokalnie na dedykowanym porcie, pełniący rolę zarówno API, jak i serwera plików statycznych dla frontendu.
3. **Wrapper Systemowy (macOS .app):** Struktura katalogów oszukująca system macOS, sprawiająca, że zestaw skryptów wygląda i zachowuje się jak natywna aplikacja okienkowa.

---

## Krok 1: Przygotowanie Lekkiego Backendu
Zamiast korzystać z głównego, skomplikowanego backendu z bazą danych, tworzymy dedykowany, minimalny plik np. `server.py` w nowym katalogu `backend/`.

**Wymagania dla Lekkiego Backendu:**
- **Serwowanie Statyczne:** Musi potrafić zaserwować pliki skompilowanego frontendu (`index.html` oraz foldery `static/`). W FastAPI używamy do tego `StaticFiles` i specjalnej trasy catch-all dla frontendu.
- **CORS:** Skonfigurowany Middleware CORS pozwalający na zapytania z `localhost` i `127.0.0.1`.
- **Lokalny Port:** Aplikacja powinna uruchamiać się na unikalnym, wysokim porcie (np. `8080` lub `8005`), aby nie kolidować z głównymi usługami środowiska (8001/8002).
- **Zależności:** Powinna posiadać własny plik `requirements.txt` ze zredukowaną listą paczek, by instalacja trwała krótko.

## Krok 2: Adaptacja i Kompilacja Frontendu
Frontend webowy wymaga dostosowania, zanim zostanie "zamknięty" w aplikacji standalone.

- **Relatywne Ścieżki API:** Kod frontendowy musi umieć wykryć, że działa lokalnie. URL do API powinien wskazywać na port, na którym działa lekki backend (np. `http://localhost:8080`). Zamiast polegać na zmiennych `.env` przy budowaniu, aplikacja może dynamicznie określać adres na podstawie `window.location.hostname`.
- **Budowanie:** Wykonujemy `npm run build` w projekcie React.
- **Integracja:** Kopiujemy całą zawartość wygenerowanego folderu `build/` do katalogu dostępnego dla serwera statycznego w kroku 1.

## Krok 3: Budowa Wrappera `.app` (macOS)
To kluczowy krok, który zamienia skrypty w "klikalną" aplikację. Struktura musi wyglądać następująco:

```text
MojaAplikacja.app/
└── Contents/
    ├── Info.plist
    ├── Resources/
    │   └── icon.icns
    └── MacOS/
        ├── launch.command  <-- Skrypt główny (EntryPoint)
        └── src/            <-- Nasz backend i frontend
```

### 3.1 Skrypt Uruchomieniowy (`launch.command`)
Ten plik bashowy to serce aplikacji. Jego zadania to:
1. Pobranie bezwzględnej ścieżki do swojego katalogu (`DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"`).
2. Sprawdzenie, czy zainstalowany jest Python 3.
3. Utworzenie i aktywacja wirtualnego środowiska (`venv`), aby nie śmiecić w systemie globalnym.
4. Pobranie opcjonalnych binariów systemowych, jeśli aplikacja ich wymaga (np. `ffmpeg` z użyciem `curl` i `unzip`).
5. Instalacja zależności (`pip install -r requirements.txt`).
6. Uruchomienie serwera FastAPI (`uvicorn server:app`) w tle.
7. Otwarcie domyślnej przeglądarki użytkownika, wskazującej na uruchomiony lokalny port (`open "http://localhost:8080"`).
8. Posiadanie pętli przechwytującej sygnały (np. `trap 'kill $UVICORN_PID' EXIT`), która grzecznie zamknie serwer w tle, gdy użytkownik zamknie okno terminala aplikacji.
9. **Krytyczne:** Plik `launch.command` musi mieć nadane prawa wykonywania (`chmod +x`).

### 3.2 Metadane (`Info.plist`)
Prosty plik XML definiujący aplikację dla systemu operacyjnego. Musi wskazywać na `launch.command` jako `CFBundleExecutable`.
Ważne atrybuty:
- `CFBundleName` (Nazwa aplikacji)
- `CFBundleIconFile` (Nazwa pliku z ikoną z folderu Resources)
- `CFBundleIdentifier` (np. `com.cradle.mojaaplikacja`)

### 3.3 Dystrybucja
Gotowy katalog `.app` kompresujemy do `.zip` przed wysłaniem użytkownikowi, co zabezpiecza strukturę katalogów i prawa wykonywania przed uszkodzeniem.

---

*Zastosowanie tych trzech kroków umożliwia dostarczenie złożonego środowiska React+Python jako bezobsługowej paczki instalacyjnej na macOS, gotowej do uruchomienia dwukrotnym kliknięciem.*
