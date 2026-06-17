import zipfile
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def unzip_and_cleanup(file_path):
    """
    Rozpakuje plik ZIP i usuwa oryginalny plik.
    
    Args:
        file_path (str): Ścieżka do pliku ZIP
        
    Returns:
        dict: {
            'was_zip': bool,
            'success': bool, 
            'extracted_files': list,
            'error': str or None
        }
    """
    try:
        file_path = Path(file_path)
        
        # Sprawdź czy to plik ZIP
        if not file_path.suffix.lower() == '.zip':
            return {
                'was_zip': False,
                'success': True,
                'extracted_files': [],
                'error': None
            }
        
        if not file_path.exists():
            return {
                'was_zip': True,
                'success': False,
                'extracted_files': [],
                'error': f'ZIP file not found: {file_path}'
            }
        
        logger.info(f"📦 Rozpakowywanie ZIP: {file_path.name}")
        
        # Folder docelowy (ten sam co ZIP)
        extract_folder = file_path.parent
        extracted_files = []
        
        # Rozpakuj ZIP
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # Lista plików w ZIP
            zip_files = zip_ref.namelist()
            logger.info(f"📦 Pliki w ZIP: {zip_files}")
            
            # Rozpakuj wszystkie pliki
            for zip_file in zip_files:
                # Sprawdź czy to nie jest folder
                if not zip_file.endswith('/'):
                    # Wyciągnij tylko nazwę pliku (bez ścieżki z ZIP)
                    filename = Path(zip_file).name
                    
                    # Sprawdź czy oryginalny ZIP miał sufiks _emis
                    is_emission_zip = "_emis" in file_path.stem.lower()
                    
                    if is_emission_zip:
                        name_parts = filename.rsplit(".", 1)
                        if len(name_parts) == 2:
                            if not name_parts[0].endswith("_emis"):
                                filename = f"{name_parts[0]}_emis.{name_parts[1]}"
                        else:
                            if not filename.endswith("_emis"):
                                filename = f"{filename}_emis"

                    # Pełna ścieżka docelowa
                    target_path = extract_folder / filename
                    
                    # Przeczytaj zawartość pliku z ZIP
                    with zip_ref.open(zip_file) as source:
                        with open(target_path, 'wb') as target:
                            target.write(source.read())
                    
                    extracted_files.append(str(target_path))
                    logger.info(f"📦 Rozpakowano: {filename}")
        
        # Usuń oryginalny ZIP
        try:
            file_path.unlink()
            logger.info(f"📦 Usunięto ZIP: {file_path.name}")
        except Exception as unlink_err:
             logger.warning(f"⚠️ Nie udało się usunąć pliku ZIP {file_path.name}: {unlink_err}")
        
        return {
            'was_zip': True,
            'success': True,
            'extracted_files': extracted_files,
            'error': None
        }
        
    except zipfile.BadZipFile:
        logger.error(f"❌ Nieprawidłowy plik ZIP: {file_path}")
        return {
            'was_zip': True,
            'success': False,
            'extracted_files': [],
            'error': 'Invalid ZIP file'
        }
    except Exception as e:
        logger.error(f"❌ Błąd podczas rozpakowywania ZIP {file_path}: {e}")
        return {
            'was_zip': True,
            'success': False,
            'extracted_files': [],
            'error': str(e)
        }

def check_and_unzip_folder(folder_path):
    """
    Sprawdza folder pod kątem plików ZIP i rozpakuje je wszystkie.
    Pomocna funkcja dla Extension notifications.
    
    Args:
        folder_path (str): Ścieżka do folderu do sprawdzenia
        
    Returns:
        dict: {
            'processed_zips': int,
            'total_extracted': int,
            'extracted_files': list,
            'errors': list
        }
    """
    try:
        folder_path = Path(folder_path)
        
        if not folder_path.exists():
            return {
                'processed_zips': 0,
                'total_extracted': 0,
                'extracted_files': [],
                'errors': [f'Folder not found: {folder_path}']
            }
        
        # Znajdź wszystkie pliki ZIP w folderze
        zip_files = list(folder_path.glob('*.zip'))
        
        if not zip_files:
            logger.debug(f"📦 Brak plików ZIP w folderze: {folder_path}")
            return {
                'processed_zips': 0,
                'total_extracted': 0,
                'extracted_files': [],
                'errors': []
            }
        
        logger.info(f"📦 Znaleziono {len(zip_files)} plików ZIP w folderze: {folder_path}")
        
        processed_zips = 0
        total_extracted = 0
        all_extracted_files = []
        errors = []
        
        # Rozpakuj każdy ZIP
        for zip_file in zip_files:
            result = unzip_and_cleanup(str(zip_file))
            
            if result['was_zip']:
                processed_zips += 1
                
                if result['success']:
                    total_extracted += len(result['extracted_files'])
                    all_extracted_files.extend(result['extracted_files'])
                else:
                    errors.append(f"ZIP {zip_file.name}: {result['error']}")
        
        logger.info(f"📦 Przetworzono {processed_zips} ZIP-ów, wyciągnięto {total_extracted} plików")
        
        return {
            'processed_zips': processed_zips,
            'total_extracted': total_extracted,
            'extracted_files': all_extracted_files,
            'errors': errors
        }
        
    except Exception as e:
        logger.error(f"❌ Błąd podczas sprawdzania folderu ZIP: {e}")
        return {
            'processed_zips': 0,
            'total_extracted': 0,
            'extracted_files': [],
            'errors': [str(e)]
        }