import asyncio
import os
from pathlib import Path
from src.video_compare_automator import VideoCompareAutomator

async def test_video_compare_full():
    """Kompletny test Video Compare automacji"""
    print("🚀 === TEST VIDEO COMPARE AUTOMATION ===")
    
    automator = VideoCompareAutomator()
    
    try:
        # === TEST 1: Setup przeglądarki ===
        print("\n📁 Test 1: Setup przeglądarki...")
        setup_success = await automator.setup_browser(headless=False)  # False żeby widzieć
        
        if not setup_success:
            print("❌ Setup przeglądarki nie powiódł się!")
            return False
        print("✅ Setup przeglądarki OK")
        
        # === TEST 2: Nawigacja do Video Compare ===
        print("\n🌐 Test 2: Nawigacja do Video Compare...")
        test_cradle_id = "test123"  # Test ID
        nav_success = await automator.navigate_to_video_compare(test_cradle_id)
        
        if not nav_success:
            print("❌ Nawigacja nie powiodła się!")
            await automator.close()
            return False
        print("✅ Nawigacja OK")
        
        # === TEST 3: Sprawdzenie drop zones ===
        print("\n🎯 Test 3: Wykrywanie drop zones...")
        await asyncio.sleep(5)  # Więcej czasu na załadowanie
        
        drop_zones = await automator.page.evaluate('''() => {
            const elements = Array.from(document.querySelectorAll('*'));
            const dropZones = elements.filter(el => 
                el.textContent && 
                el.textContent.includes('Drop files here or click to upload') &&
                el.offsetWidth > 100 && 
                el.offsetHeight > 100
            );
            
            return dropZones.map(zone => ({
                text: zone.textContent.trim().substring(0, 50),
                left: zone.getBoundingClientRect().left,
                top: zone.getBoundingClientRect().top,
                width: zone.getBoundingClientRect().width,
                height: zone.getBoundingClientRect().height,
                centerX: zone.getBoundingClientRect().left + zone.getBoundingClientRect().width / 2,
                centerY: zone.getBoundingClientRect().top + zone.getBoundingClientRect().height / 2
            }));
        }''')
        
        if not drop_zones or len(drop_zones) < 2:
            print(f"❌ Nie znaleziono drop zones! Znaleziono: {len(drop_zones) if drop_zones else 0}")
            
            # Debug: sprawdź co jest na stronie
            page_title = await automator.page.title()
            page_url = automator.page.url
            print(f"📄 Tytuł strony: {page_title}")
            print(f"🌐 URL: {page_url}")
            
            # Sprawdź czy jest jakiś tekst z "drop" lub "upload"
            upload_text = await automator.page.evaluate('''() => {
                const bodyText = document.body.innerText.toLowerCase();
                const lines = bodyText.split('\\n').filter(line => 
                    line.includes('drop') || 
                    line.includes('upload') || 
                    line.includes('file')
                );
                return lines.slice(0, 10);  // Pierwsze 10 linii
            }''')
            print(f"🔍 Tekst związany z upload: {upload_text}")
            
        else:
            print(f"✅ Znaleziono {len(drop_zones)} drop zones")
            for i, zone in enumerate(drop_zones):
                print(f"   Zone {i}: '{zone['text']}' centerX={zone['centerX']}, centerY={zone['centerY']}")
        
        # === TEST 4: Sprawdzenie przycisku Submit ===
        print("\n🔘 Test 4: Wykrywanie przycisku Submit...")
        
        submit_buttons = await automator.page.evaluate('''() => {
            const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a'));
            return buttons.map(btn => ({
                text: btn.textContent || btn.value || '',
                tagName: btn.tagName,
                type: btn.type || 'none',
                className: btn.className || ''
            })).filter(btn => btn.text.trim().length > 0);
        }''')
        
        print(f"🔍 Znaleziono {len(submit_buttons)} przycisków:")
        for btn in submit_buttons:
            print(f"   - {btn['tagName']} [{btn['type']}]: '{btn['text']}' class='{btn['className']}'")
        
        submit_found = any('submit' in btn['text'].lower() for btn in submit_buttons)
        if submit_found:
            print("✅ Znaleziono przycisk Submit")
        else:
            print("❌ Nie znaleziono przycisku Submit")
        
        # === PAUZA dla obserwacji ===
        print("\n⏸️  Pauza 15 sekund - sprawdź wizualnie stronę Video Compare...")
        print("   - Czy widzisz 2 panele upload?")
        print("   - Czy widzisz przycisk Submit?")
        print("   - Jak wygląda interface?")
        await asyncio.sleep(15)
        
        print("✅ Test Video Compare zakończony!")
        return True
        
    except Exception as e:
        print(f"❌ Błąd podczas testu: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n🔄 Zamykanie przeglądarki...")
        await automator.close()

async def test_with_real_files():
    """Test z prawdziwymi plikami MP4"""
    print("\n🎬 === TEST Z PRAWDZIWYMI PLIKAMI ===")
    
    # Znajdź pliki MP4 w Downloads
    downloads_dir = Path.home() / "Downloads"
    mp4_files = list(downloads_dir.glob("*.mp4"))[:10]  # Pierwsze 10 plików
    
    if len(mp4_files) < 2:
        print(f"❌ Potrzeba minimum 2 plików MP4, znaleziono: {len(mp4_files)}")
        return
    
    # Wybierz 2 najmniejsze pliki (szybszy upload)
    mp4_files.sort(key=lambda f: f.stat().st_size)
    acceptance_file = mp4_files[0]
    emission_file = mp4_files[1]
    
    print(f"✅ Wybrano pliki:")
    print(f"📁 Acceptance: {acceptance_file.name} ({acceptance_file.stat().st_size // 1024} KB)")
    print(f"📁 Emission: {emission_file.name} ({emission_file.stat().st_size // 1024} KB)")
    
    automator = VideoCompareAutomator()
    
    try:
        # Test pełnego upload procesu
        print("\n🚀 Rozpoczynam pełny test upload...")
        result = await automator.handle_hybrid_upload(
            str(acceptance_file), 
            str(emission_file), 
            "test-real-files"
        )
        
        if result['success']:
            print("✅ Pełny test upload zakończony sukcesem!")
            print(f"💬 Message: {result.get('message')}")
        else:
            print(f"❌ Test upload nie powiódł się: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Błąd podczas testu z plikami: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await automator.close()

def main():
    """Główna funkcja testowa"""
    print("🎯 === VIDEO COMPARE TESTER ===")
    print("Wybierz test:")
    print("1. Test podstawowy (nawigacja + wykrywanie elementów)")
    print("2. Test z prawdziwymi plikami (pełny upload)")
    print("3. Oba testy")
    
    choice = input("\nWybór (1/2/3): ").strip()
    
    if choice == "1":
        asyncio.run(test_video_compare_full())
    elif choice == "2":
        asyncio.run(test_with_real_files())
    elif choice == "3":
        asyncio.run(test_video_compare_full())
        print("\n" + "="*50)
        asyncio.run(test_with_real_files())
    else:
        print("❌ Nieprawidłowy wybór!")

if __name__ == "__main__":
    main()