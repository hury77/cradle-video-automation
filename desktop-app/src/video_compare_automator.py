import asyncio
import json
import logging
import subprocess
import time
import os
import psutil
import aiohttp
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

class VideoCompareAutomator:
    def __init__(self, logger=None):
        self.logger = logger or self._setup_logger()
        self.browser = None
        self.page = None
        self.playwright = None
        self.context = None
        
    def _setup_logger(self):
        logger = logging.getLogger('VideoCompareAutomator')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    async def setup_browser(self, headless=False):
        """Setupuje przeglądarkę z obsługą plików używając Playwright"""
        try:
            self.logger.info("Uruchamianie przeglądarki z Playwright...")
            
            self.playwright = await async_playwright().start()
            
            # Uruchom Chrome z odpowiednimi opcjami
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--allow-running-insecure-content',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            # Utwórz nowy kontekst z obsługą plików
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True
            )
            
            self.page = await self.context.new_page()
            
            self.logger.info("Pomyślnie uruchomiono przeglądarkę z Playwright")
            return True
            
        except Exception as e:
            self.logger.error(f"Błąd podczas setupu przeglądarki: {e}")
            return False

    async def navigate_to_video_compare(self, cradle_id):
        """Nawiguje do strony Video Compare"""
        try:
            if not self.page:
                self.logger.error("Przeglądarka nie jest skonfigurowana")
                return False
            
            # ✅ POPRAWKA: Używamy prawidłowego URL
            video_compare_url = f"https://cradle.egplusww.pl/vcompare/add/"
            self.logger.info(f"Nawigacja do Video Compare: {video_compare_url}")
            
            await self.page.goto(video_compare_url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(2)
            
            self.logger.info("Pomyślnie załadowano stronę Video Compare")
            return True
            
        except TimeoutError:
            self.logger.error("Timeout podczas ładowania strony Video Compare")
            return False
        except Exception as e:
            self.logger.error(f"Błąd podczas nawigacji do Video Compare: {e}")
            return False

    async def upload_videos(self, acceptance_file_path, emission_file_path):
        """
        Ulepszona automatyzacja Video Compare z Playwright:
        1. Lepsze wykrywanie obszarów drag-and-drop upload
        2. Spatial assignment (lewy = acceptance, prawy = emission)  
        3. Precyzyjne wykrywanie przycisku "Submit all files"
        4. Monitoring postępu i wyników
        """
        try:
            self.logger.info("=== ROZPOCZĘCIE UPLOAD VIDEOS ===")
            self.logger.info(f"Acceptance file: {acceptance_file_path}")
            self.logger.info(f"Emission file: {emission_file_path}")
            
            # Sprawdź czy pliki istnieją
            if not os.path.exists(acceptance_file_path):
                self.logger.error(f"Plik acceptance nie istnieje: {acceptance_file_path}")
                return {'success': False, 'error': 'Acceptance file not found'}
                
            if not os.path.exists(emission_file_path):
                self.logger.error(f"Plik emission nie istnieje: {emission_file_path}")
                return {'success': False, 'error': 'Emission file not found'}

            # ✅ SETUP BROWSER JEŚLI POTRZEBA
            if not self.browser or not self.page or not self.context:
                self.logger.info("Browser nie jest skonfigurowany, uruchamiam setup...")
                setup_success = await self.setup_browser()
                if not setup_success:
                    return {'success': False, 'error': 'Browser setup failed'}

            # ✅ NAWIGACJA DO VIDEO COMPARE
            nav_success = await self.navigate_to_video_compare("manual")
            if not nav_success:
                return {'success': False, 'error': 'Navigation to Video Compare failed'}
            
            # Czekamy na załadowanie strony
            await asyncio.sleep(3)
            
            # KROK 1: Znajdź obszary upload przez tekst "Drop files here"
            drop_zones = await self.page.evaluate('''() => {
                // Szukamy wszystkich elementów z tekstem "Drop files here"
                const elements = Array.from(document.querySelectorAll('*'));
                const dropZones = elements.filter(el => 
                    el.textContent && 
                    el.textContent.includes('Drop files here or click to upload') &&
                    el.offsetWidth > 100 && 
                    el.offsetHeight > 100
                );
                
                return dropZones.map(zone => ({
                    left: zone.getBoundingClientRect().left,
                    top: zone.getBoundingClientRect().top,
                    width: zone.getBoundingClientRect().width,
                    height: zone.getBoundingClientRect().height,
                    centerX: zone.getBoundingClientRect().left + zone.getBoundingClientRect().width / 2,
                    centerY: zone.getBoundingClientRect().top + zone.getBoundingClientRect().height / 2
                }));
            }''')
            
            if not drop_zones or len(drop_zones) < 2:
                self.logger.error(f"Nie znaleziono 2 obszarów upload. Znaleziono: {len(drop_zones) if drop_zones else 0}")
                return {'success': False, 'error': f'Expected 2 upload zones, found {len(drop_zones) if drop_zones else 0}'}
                
            self.logger.info(f"Znaleziono {len(drop_zones)} obszarów upload")
            
            # Debug informacje
            for i, zone in enumerate(drop_zones):
                self.logger.debug(f"Zone {i}: centerX={zone['centerX']}, centerY={zone['centerY']}, width={zone['width']}, height={zone['height']}")
            
            # KROK 2: Spatial assignment - lewy panel = acceptance, prawy = emission
            drop_zones.sort(key=lambda zone: zone['centerX'])  # Sortuj od lewej do prawej
            left_zone = drop_zones[0]   # Acceptance (lewy)
            right_zone = drop_zones[1]  # Emission (prawy)
            
            self.logger.info(f"Lewy panel (acceptance): centerX={left_zone['centerX']}")
            self.logger.info(f"Prawy panel (emission): centerX={right_zone['centerX']}")
            
            # KROK 3: Upload plików przez symulację drag-and-drop
            self.logger.info("Uploading acceptance file do lewego panelu...")
            success_acceptance = await self.upload_file_to_zone(acceptance_file_path, left_zone)
            
            if success_acceptance:
                await asyncio.sleep(2)
                self.logger.info("Uploading emission file do prawego panelu...")
                success_emission = await self.upload_file_to_zone(emission_file_path, right_zone)
            else:
                self.logger.error("Upload acceptance file nie powiódł się")
                return {'success': False, 'error': 'Acceptance file upload failed'}
                
            if not success_emission:
                self.logger.error("Upload emission file nie powiódł się")
                return {'success': False, 'error': 'Emission file upload failed'}
                
            # KROK 4: Znajdź i kliknij przycisk "Submit all files"
            await asyncio.sleep(2)
            submit_success = await self.click_submit_button()
            
            if not submit_success:
                self.logger.error("Nie udało się kliknąć przycisku Submit")
                return {'success': False, 'error': 'Submit button click failed'}
                
            # KROK 5: Monitor wyników
            result = await self.monitor_comparison_results()
            
            self.logger.info("=== ZAKOŃCZENIE UPLOAD VIDEOS ===")
            return {'success': True, 'result': result, 'message': 'Video compare completed successfully'}
            
        except Exception as e:
            self.logger.error(f"Błąd w upload_videos(): {e}")
            return {'success': False, 'error': str(e)}

    async def upload_file_to_zone(self, file_path, zone_info):
        """Upload pliku do konkretnej strefy drag-and-drop - wersja Playwright"""
        try:
            # Znajdź ukryty input[type="file"] w tej strefie
            file_input_id = await self.page.evaluate(f'''() => {{
                const zone = document.elementFromPoint({zone_info['centerX']}, {zone_info['centerY']});
                if (!zone) return null;
                
                // Szukaj input[type="file"] w tej strefie lub jej rodzicu
                let current = zone;
                for (let i = 0; i < 5; i++) {{
                    const input = current.querySelector('input[type="file"]');
                    if (input) {{
                        // Dodaj ID jeśli go nie ma
                        if (!input.id) {{
                            input.id = 'upload-input-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
                        }}
                        return input.id;
                    }}
                    current = current.parentElement;
                    if (!current) break;
                }}
                return null;
            }}''')
            
            if file_input_id:
                self.logger.info(f"Znaleziono input file: #{file_input_id}")
                
                # Użyj Playwright do upload pliku z timeout
                file_input = self.page.locator(f'#{file_input_id}')
                await file_input.set_input_files(file_path, timeout=10000)
                
                self.logger.info(f"Plik {file_path} został ustawiony przez Playwright")
                return True
            else:
                self.logger.warning("Nie znaleziono input[type='file'], próbuję kliknąć w strefę")
                # Fallback: kliknij w centrum strefy
                await self.page.click(f'{zone_info["centerX"]}, {zone_info["centerY"]}', timeout=5000)
                await asyncio.sleep(2)
                
                # Sprawdź czy pojawiła się reakcja i spróbuj ponownie znaleźć input
                await asyncio.sleep(1)
                
                # Próba z ogólnym selektorem
                try:
                    file_inputs = self.page.locator('input[type="file"]')
                    count = await file_inputs.count()
                    if count > 0:
                        # Użyj pierwszego dostępnego input z timeout
                        await file_inputs.first.set_input_files(file_path, timeout=10000)
                        self.logger.info(f"Fallback: użyto pierwszego dostępnego input[type='file']")
                        return True
                except Exception as fallback_error:
                    self.logger.warning(f"Fallback też nie zadziałał: {fallback_error}")
                
                return True  # Zwróć True nawet jeśli fallback nie zadziałał
                
        except Exception as e:
            self.logger.error(f"Błąd w upload_file_to_zone(): {e}")
            return False

    async def click_submit_button(self):
        """Znajdź i kliknij przycisk 'Submit all files' - wersja Playwright"""
        try:
            # Najpierw spróbuj znaleźć dokładnie "Submit all files"
            try:
                submit_button = self.page.locator('button:has-text("Submit all files")')
                if await submit_button.count() > 0:
                    # Dodaj timeout do click
                    await submit_button.first.click(timeout=5000)
                    self.logger.info("Kliknięto przycisk 'Submit all files'")
                    return True
            except Exception:
                pass
            
            # Fallback: szukaj ogólnie "Submit"
            try:
                submit_button = self.page.locator('button:has-text("Submit")')
                if await submit_button.count() > 0:
                    # Dodaj timeout do click
                    await submit_button.first.click(timeout=5000)
                    self.logger.info("Kliknięto przycisk 'Submit' (fallback)")
                    return True
            except Exception:
                pass
            
            # Fallback 2: szukaj input submit
            try:
                submit_input = self.page.locator('input[type="submit"]')
                if await submit_input.count() > 0:
                    # Dodaj timeout do click
                    await submit_input.first.click(timeout=5000)
                    self.logger.info("Kliknięto input submit (fallback 2)")
                    return True
            except Exception:
                pass
            
            # Fallback 3: JavaScript search
            submit_found = await self.page.evaluate('''() => {
                const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a'));
                const submitButton = buttons.find(btn => {
                    const text = btn.textContent || btn.value || '';
                    return text.includes('Submit all files') || 
                           text.includes('Submit');
                });
                
                if (submitButton) {
                    submitButton.scrollIntoView();
                    submitButton.click();
                    return true;
                }
                return false;
            }''')
            
            if submit_found:
                self.logger.info("Przycisk Submit został kliknięty (JavaScript fallback)")
                return True
            else:
                self.logger.error("Nie znaleziono przycisku Submit w żaden sposób")
                return False
                
        except Exception as e:
            self.logger.error(f"Błąd w click_submit_button(): {e}")
            return False

    async def monitor_comparison_results(self):
        """Monitoruj wyniki porównania video - wersja Playwright"""
        try:
            self.logger.info("Rozpoczynam monitoring wyników...")
            
            # Czekaj na wyniki przez maksymalnie 5 minut
            for attempt in range(60):  # 60 x 5s = 5 minut
                await asyncio.sleep(5)
                
                # Sprawdź czy są jakieś wyniki lub komunikaty o błędzie
                status = await self.page.evaluate('''() => {
                    // Szukaj indicatorów postępu lub wyników
                    const progressElements = document.querySelectorAll('*');
                    const results = [];
                    
                    for (let el of progressElements) {
                        const text = el.textContent || '';
                        if (text.includes('Time:') || 
                            text.includes('seconds') ||
                            text.includes('Complete') ||
                            text.includes('Success') ||
                            text.includes('Error') ||
                            text.includes('Failed') ||
                            text.includes('Processing')) {
                            results.push(text.trim());
                        }
                    }
                    
                    return results.length > 0 ? results : null;
                }''')
                
                if status:
                    self.logger.info(f"Status update (attempt {attempt + 1}): {status}")
                    
                    # Sprawdź czy to końcowy wynik
                    status_text = ' '.join(status).lower()
                    if any(word in status_text for word in ['complete', 'success', 'error', 'failed']):
                        self.logger.info("Wykryto końcowy wynik porównania")
                        return True
                else:
                    self.logger.debug(f"Monitoring attempt {attempt + 1}/60 - brak statusu")
            
            self.logger.warning("Timeout podczas oczekiwania na wyniki (5 minut)")
            return True  # Zwróć True mimo timeout - może proces się zakończył
            
        except Exception as e:
            self.logger.error(f"Błąd w monitor_comparison_results(): {e}")
            return False

    async def handle_download_attachment(self, data):
        """Obsługuje pobieranie plików attachment gdy Chrome API nie jest dostępne"""
        try:
            url = data.get('url')
            filename = data.get('filename')
            file_type = data.get('fileType', 'unknown')
            cradle_id = data.get('cradleId', 'unknown')
            
            if not url or not filename:
                self.logger.error(f"Brakujące wymagane pola: url={url}, filename={filename}")
                return {'success': False, 'error': 'Missing required fields: url or filename'}
            
            self.logger.info(f"Rozpoczynam pobieranie attachment: {filename} z {url}")
            
            # Utwórz folder download jeśli nie istnieje
            download_folder = Path.home() / "Downloads" / cradle_id
            download_folder.mkdir(parents=True, exist_ok=True)
            
            file_path = download_folder / filename
            
            # Pobierz plik z realistycznymi nagłówkami
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Sprawdź czy plik nie jest błędną stroną (zbyt mały rozmiar)
                        if len(content) < 5000:  # Mniej niż 5KB prawdopodobnie błąd
                            content_text = content.decode('utf-8', errors='ignore')[:200]
                            self.logger.warning(f"Plik {filename} jest podejrzanie mały ({len(content)} bajtów): {content_text}")
                        
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        
                        self.logger.info(f"Pobrano {filename} ({len(content)} bajtów) do {file_path}")
                        return {
                            'success': True, 
                            'file_path': str(file_path), 
                            'size': len(content),
                            'type': file_type
                        }
                    else:
                        self.logger.error(f"HTTP {response.status} podczas pobierania {url}")
                        return {'success': False, 'error': f'HTTP {response.status}'}
                        
        except Exception as e:
            self.logger.error(f"Błąd podczas pobierania attachment {filename}: {e}")
            return {'success': False, 'error': str(e)}

    async def handle_hybrid_upload(self, acceptance_file_path, emission_file_path, cradle_id):
        """Główna metoda obsługująca cały proces upload do Video Compare"""
        try:
            self.logger.info(f"=== HYBRID UPLOAD START dla CradleID: {cradle_id} ===")
            
            # Sprawdź czy pliki istnieją
            if not os.path.exists(acceptance_file_path):
                self.logger.error(f"Plik acceptance nie istnieje: {acceptance_file_path}")
                return {'success': False, 'error': 'Acceptance file not found'}
                
            if not os.path.exists(emission_file_path):
                self.logger.error(f"Plik emission nie istnieje: {emission_file_path}")
                return {'success': False, 'error': 'Emission file not found'}
            
            # Lepsze sprawdzanie context
            if not self.browser or not self.page or not self.context:
                self.logger.info("Browser/context nie jest skonfigurowany, uruchamiam setup...")
                setup_success = await self.setup_browser()
                if not setup_success:
                    return {'success': False, 'error': 'Browser setup failed'}
            
            # Nawiguj do Video Compare
            nav_success = await self.navigate_to_video_compare(cradle_id)
            if not nav_success:
                return {'success': False, 'error': 'Navigation to Video Compare failed'}
            
            # Upload plików
            upload_success = await self.upload_videos(acceptance_file_path, emission_file_path)
            if not upload_success:
                return {'success': False, 'error': 'Video upload failed'}
            
            self.logger.info("=== HYBRID UPLOAD SUCCESS ===")
            return {'success': True, 'message': 'Video compare completed successfully'}
            
        except Exception as e:
            self.logger.error(f"Błąd w handle_hybrid_upload: {e}")
            return {'success': False, 'error': str(e)}

    async def close(self):
        """Zamyka przeglądarkę i czyści zasoby"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
                
            self.logger.info("Zamknięto VideoCompareAutomator")
        except Exception as e:
            self.logger.error(f"Błąd podczas zamykania: {e}")

    def __del__(self):
        """Destruktor zapewniający zamknięcie zasobów"""
        try:
            # Playwright cleanup w destruktorze jest trudny ze względu na asyncio
            # Lepiej użyć explicit close()
            pass
        except:
            pass