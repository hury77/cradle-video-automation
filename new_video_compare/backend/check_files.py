import os
from pathlib import Path
from models.database import SessionLocal
from models.models import File as FileModel

def check_files():
    with SessionLocal() as db:
        for file_id in [855, 856]:
            file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
            if not file_record:
                print(f"ID {file_id}: Nie znaleziono w bazie danych")
                continue
            
            print(f"\n--- ID {file_id} ---")
            print(f"Nazwa: {file_record.filename}")
            print(f"Oryginalna nazwa: {file_record.original_name}")
            print(f"Ścieżka w bazie: {file_record.file_path}")
            print(f"Czy przetworzony (is_processed): {file_record.is_processed}")
            print(f"Format: {file_record.file_format}")
            print(f"Kodek: {file_record.codec}")
            
            p = Path(file_record.file_path)
            if not p.is_absolute():
                p = Path("/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend") / p
            print(f"Czy ścieżka istnieje: {p.exists()} ({p.absolute()})")
            
            # Sprawdźmy proxy
            from api.v1.files import get_proxy_path, needs_transcoding
            needs_t = needs_transcoding(file_record)
            print(f"Czy wymaga transkodowania (needs_transcoding): {needs_t}")
            if needs_t:
                proxy_path = get_proxy_path(p)
                print(f"Ścieżka proxy: {proxy_path}")
                print(f"Czy proxy istnieje na dysku: {proxy_path.exists()}")

if __name__ == "__main__":
    check_files()
