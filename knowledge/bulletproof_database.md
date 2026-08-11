# Architektura: Bulletproof Database

Z uwagi na incydent z 10 sierpnia 2026 r., kiedy to konflikt w gałęziach systemu Git (ang. *footgun*) zniszczył produkcyjną bazę danych, wdrożono architekturę wielowarstwowego pancerza ochronnego (Defense-in-Depth). 

Każdy Agent (i człowiek) modyfikujący system musi przestrzegać poniższych założeń:

## 1. Lokacja Bazy (Immunitet Git)
Aktywna, produkcyjna baza danych **NIE ZNAJDUJE SIĘ** w folderze repozytorium.
- Ścieżka bazy: `~/.cradle_data/new_video_compare.db`
- **Zasada:** Nigdy nie konfiguruj aplikacji (`config.py`) na pliki `.db` leżące w repo. Kod i dane żyją osobno.

## 2. Zamrożenie Kopii Zapasowych (Immutable Backups)
Pliki kopii zapasowej w `~/.cradle_data/backups/` podlegają ścisłemu reżimowi systemowemu:
- Otrzymują natychmiast flagę systemową jądra macOS `uchg` (tzw. immutable flag).
- Oznacza to, że plik nie może być usunięty, zmodyfikowany ani nadpisany przez standardowe `rm -rf`, `os.unlink` czy `shutil.rmtree`, nawet przez właściciela pliku.
- **Zasada:** Aby usunąć plik backupu (np. w logice retencji), skrypt musi jawnie najpierw zdjąć tę flagę wywołując `chflags nouchg <plik>`.

## 3. Zabezpieczenie przed pętlą retencji
- Skrypt czyszczący stare backupy (retencja) ma kategoryczny zakaz usuwania **trzech (3) najnowszych kopii**. Nawet jeśli błąd w skrypcie źle policzy daty, baza danych zawsze ma zachowane minimum 3 stany wstecz.

## 4. Git Hooks i Startup Check
- System wykorzystuje hooki w katalogu `.githooks/` w repozytorium.
- Skrypty `post-checkout` i `pre-merge-commit` tworzą szybkie zrzuty (snapshots) bazy przed jakąkolwiek ryzykowną akcją Gita.
- **Zasada:** Backend aplikacji w `main.py` posiada procedurę weryfikującą na starcie, czy Git używa `core.hooksPath`. Jeśli nie (np. z powodu sklonowania na nowy serwer), backend samoczynnie to ustawia i łata instalację przez `scripts/install_hooks.sh`. Nie usuwaj tego kodu.
