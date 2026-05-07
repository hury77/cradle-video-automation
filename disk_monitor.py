import os
import time
from pathlib import Path

# Zgodnie z SOUL.md: Skrypt informuje o przekroczeniu limitu, podaje co usunie, wymaga zgody.
# Baza Danych (KB) nigdy nie jest usuwana.

# Konfiguracja progu (GB)
LIMIT_GB = 25
TARGET_GB = 20
LIMIT_BYTES = LIMIT_GB * 1024**3
TARGET_BYTES = TARGET_GB * 1024**3
LOG_LIMIT_BYTES = 50 * 1024**2 # Logi większe niż 50 MB

# Określamy ścieżkę do głównego katalogu projektu
PROJECT_ROOT = Path(__file__).parent.resolve()

UPLOAD_DIRS = [
    PROJECT_ROOT / "uploads",
    PROJECT_ROOT / "new_video_compare" / "backend" / "uploads"
]

def get_dir_size(path: Path) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total += os.path.getsize(fp)
    return total

def format_size(bytes_size: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def main():
    print(f"🔍 Skanowanie katalogu: {PROJECT_ROOT}...")
    current_size = get_dir_size(PROJECT_ROOT)
    
    print(f"📊 Obecny rozmiar projektu: {format_size(current_size)}")
    if current_size < LIMIT_BYTES:
        print(f"✅ Rozmiar mniejszy niż {LIMIT_GB} GB. Nie ma potrzeby sprzątania.")
        return
        
    print(f"\n⚠️ PRZEKROCZONO LIMIT {LIMIT_GB} GB! Szukam plików do usunięcia...")
    
    bytes_to_free = current_size - TARGET_BYTES
    print(f"🎯 Cel odzyskania miejsca: {format_size(bytes_to_free)} (aby zejść poniżej {TARGET_GB} GB)\n")
    
    # 1. Znajdź masywne logi > 50MB (zabezpiecz przed usuwaniem z .venv itp)
    logs_to_delete = []
    for dirpath, _, filenames in os.walk(PROJECT_ROOT):
        # Ignorujemy katalogi wirtualne i git
        if ".venv" in dirpath or ".git" in dirpath or "venv" in dirpath:
            continue
        for f in filenames:
            if f.endswith(".log"):
                fp = Path(dirpath) / f
                try:
                    size = fp.stat().st_size
                    if size > LOG_LIMIT_BYTES:
                        logs_to_delete.append((fp, size))
                except OSError:
                    pass
                    
    # 2. Znajdź pliki wideo z katalogów uploads
    videos = []
    for udir in UPLOAD_DIRS:
        if not udir.exists():
            continue
        for f in udir.iterdir():
            if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".mxf", ".zip"]:
                videos.append((f, f.stat().st_mtime, f.stat().st_size))
                
    # Sortuj wideo od najstarszych (zgodnie z decyzją Usera - usuwamy zawsze najstarsze)
    videos.sort(key=lambda x: x[1])
    
    files_to_delete = []
    freed_so_far = 0
    
    # Krok 1: Dodaj masywne logi do listy
    for fp, size in logs_to_delete:
        files_to_delete.append((fp, size))
        freed_so_far += size
        
    # Krok 2: Dobieraj najstarsze pliki wideo dopóki nie uwolnisz wystarczającej ilości miejsca
    for f, _, size in videos:
        if freed_so_far >= bytes_to_free:
            break
        files_to_delete.append((f, size))
        freed_so_far += size
        
    if not files_to_delete:
        print("Brak bezpiecznych plików (dużych logów lub starych wideo) do usunięcia. Usuwanie ręczne może być konieczne.")
        return
        
    print("🗑️ --- ZNALEZIONO PLIKI DO USUNIĘCIA ---")
    for f, size in files_to_delete:
        # Pokaż ścieżkę relatywną dla lepszej czytelności, jeśli to możliwe
        try:
            display_name = f.relative_to(PROJECT_ROOT)
        except ValueError:
            display_name = f
        print(f" - {display_name} ({format_size(size)})")
        
    print("-" * 50)
    print(f"Podsumowanie:")
    print(f"Liczba plików do usunięcia: {len(files_to_delete)}")
    print(f"Przewidywane uwolnione miejsce: {format_size(freed_so_far)}")
    print(f"🛡️  SOUL.md CHECK: Baza wiedzy (KB - qa_decisions / pliki .db) jest BEZPIECZNA.")
    print("-" * 50)
    
    ans = input("\nCzy chcesz kontynuować i usunąć te pliki? [T/n]: ")
    if ans.lower() == 't' or ans.lower() == 'tak' or ans == '':
        for f, _ in files_to_delete:
            try:
                f.unlink()
                print(f"Usunięto: {f.name}")
            except Exception as e:
                print(f"Błąd przy usuwaniu {f.name}: {e}")
        print("\n✨ Sprzątanie zakończone pomyślnie.")
    else:
        print("\n❌ Anulowano przez użytkownika. Żadne pliki nie zostały usunięte.")

if __name__ == "__main__":
    main()
