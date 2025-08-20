class CradleScanner {
    constructor() {
        this.isScanning = false;
        this.status = 'Ready';
        
        document.addEventListener('extension-command', (event) => {
            console.log('[CradleScanner] Command received:', event.detail.action);
            this.handleCommand(event.detail);
        });
        
        // Sprawdź czy po przeładowaniu strony mamy automatycznie zastosować filtr
        this.checkAutoApplyFilter();
        
        console.log('[CradleScanner] Scanner initialized');
    }
    
    async checkAutoApplyFilter() {
        const shouldAutoApply = localStorage.getItem('cradle-auto-apply-qa-filter');
        const currentUrl = window.location.href;
        const targetUrl = 'https://cradle.egplusww.pl/my-team/';
        
        console.log('[CradleScanner] Checking auto-apply filter...');
        console.log('[CradleScanner] Should auto-apply:', shouldAutoApply);
        console.log('[CradleScanner] Current URL:', currentUrl);
        console.log('[CradleScanner] Target URL:', targetUrl);
        
        if (shouldAutoApply === 'true') {
            console.log('[CradleScanner] 🔄 Auto-apply flag found!');
            
            // Usuń flagę
            localStorage.removeItem('cradle-auto-apply-qa-filter');
            
            // Sprawdź czy jesteśmy na właściwej stronie
            if (currentUrl !== targetUrl) {
                console.log('[CradleScanner] ❌ Wrong URL for auto-apply, ignoring...');
                return;
            }
            
            console.log('[CradleScanner] ✅ Correct URL, scheduling auto-apply...');
            
            // Czekaj 3 sekundy na załadowanie strony
            setTimeout(async () => {
                console.log('[CradleScanner] 🚀 Starting auto-apply filter...');
                await this.applyQAFilterOnly();
            }, 3000);
        } else {
            console.log('[CradleScanner] No auto-apply flag found');
        }
    }
    
    handleCommand(command) {
        switch(command.action) {
            case 'START_AUTOMATION':
                this.startAutomation();
                break;
            case 'STOP_AUTOMATION':
                this.stopAutomation();
                break;
            case 'FIND_ASSET':
                this.findPendingAsset();
                break;
            case 'GET_STATUS':
                this.sendStatus();
                break;
        }
    }
    
    sendStatus() {
        console.log('[CradleScanner] Current status:', this.status);
        document.dispatchEvent(new CustomEvent('extension-response', {
            detail: {
                action: 'STATUS_UPDATE',
                data: { status: this.status, isScanning: this.isScanning }
            }
        }));
    }
    
    showNotification(message, type = 'info') {
        console.log(`[CradleScanner] ${type.toUpperCase()}: ${message}`);
        document.dispatchEvent(new CustomEvent('extension-notification', {
            detail: { message, type }
        }));
    }
    
    async startAutomation() {
        const targetUrl = 'https://cradle.egplusww.pl/my-team/';
        const currentUrl = window.location.href;
        
        console.log('[CradleScanner] Starting automation...');
        console.log('[CradleScanner] Current URL:', currentUrl);
        console.log('[CradleScanner] Target URL:', targetUrl);
        
        // Sprawdź URL na samym początku
        if (currentUrl !== targetUrl) {
            console.log('[CradleScanner] ❌ Wrong page! Redirecting...');
            
            // Ustaw flagę żeby po przeładowaniu automatycznie zastosować filtr
            localStorage.setItem('cradle-auto-apply-qa-filter', 'true');
            console.log('[CradleScanner] ✅ Auto-apply flag set in localStorage');
            
            this.status = 'Redirecting to My Team Tasks...';
            this.showNotification('Redirecting to My Team Tasks - filter will be applied automatically', 'info');
            
            setTimeout(() => {
                console.log('[CradleScanner] 🔄 Redirecting now...');
                window.location.href = targetUrl;
            }, 1000);
            
            return; // Zatrzymaj dalsze wykonywanie
        }
        
        console.log('[CradleScanner] ✅ Already on correct page, applying filter...');
        // Jesteśmy na właściwej stronie - zastosuj filtr
        await this.applyQAFilterOnly();
    }
    
    async findPendingAsset() {
        console.log('[CradleScanner] 🔍 Finding pending asset...');
        this.status = 'Finding pending asset...';
        this.showNotification('Searching for pending assets...', 'info');
        
        try {
            // ZNAJDŹ WŁAŚCIWĄ TABELĘ Z ASSETAMI
            const allTables = document.querySelectorAll('table');
            console.log(`[CradleScanner] Found ${allTables.length} tables on page`);
            
            let assetsTable = null;
            
            // Sprawdź każdą tabelę
            for (let i = 0; i < allTables.length; i++) {
                const table = allTables[i];
                const rows = table.querySelectorAll('tr');
                const dataRows = Array.from(table.querySelectorAll('tr')).filter(row => 
                    row.querySelectorAll('td').length > 0
                );
                
                console.log(`[CradleScanner] Table ${i}: ${rows.length} total rows, ${dataRows.length} data rows`);
                
                // Szukamy tabeli z najwięcej wierszy danych (prawdopodobnie ta z assetami)
                if (dataRows.length > 0) {
                    // Sprawdź czy ma kolumny które oczekujemy (Cradle.ID w pierwszej kolumnie)
                    const firstDataRow = dataRows[0];
                    const firstCell = firstDataRow.querySelector('td');
                    
                    if (firstCell) {
                        const cellText = firstCell.textContent.trim();
                        console.log(`[CradleScanner] Table ${i} first cell:`, cellText);
                        
                        // Sprawdź czy pierwsza komórka wygląda jak Cradle.ID (liczba)
                        if (/^\d+$/.test(cellText)) {
                            console.log(`[CradleScanner] ✅ Found assets table (Table ${i}) with Cradle.ID: ${cellText}`);
                            assetsTable = table;
                            break;
                        }
                    }
                }
            }
            
            if (!assetsTable) {
                throw new Error('Assets table not found among ' + allTables.length + ' tables on page');
            }
            
            // Teraz używamy właściwej tabeli
            console.log('[CradleScanner] Using assets table, waiting for data to load...');
            
            // CZEKAJ na załadowanie wierszy tabeli
            let rows = [];
            let attempts = 0;
            const maxAttempts = 20;
            
            while (rows.length === 0 && attempts < maxAttempts) {
                rows = Array.from(assetsTable.querySelectorAll('tbody tr'));
                
                if (rows.length === 0) {
                    rows = Array.from(assetsTable.querySelectorAll('tr')).filter(row => {
                        const cells = row.querySelectorAll('td');
                        return cells.length > 0;
                    });
                }
                
                if (rows.length === 0) {
                    console.log(`[CradleScanner] Attempt ${attempts + 1}: No rows in assets table, waiting...`);
                    await this.wait(500);
                    attempts++;
                } else {
                    console.log(`[CradleScanner] Success! Found ${rows.length} rows in assets table`);
                    break;
                }
            }
            
            if (rows.length === 0) {
                throw new Error('No data rows found in assets table after waiting');
            }
            
            // Tabela jest już posortowana według Prod.deadline (najwcześniejsza data na górze)
            // Szukamy pierwszego wiersza ze statusem "Pending"
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const cells = row.querySelectorAll('td');
                
                if (cells.length === 0) continue;
                
                // Pierwsza kolumna - Cradle.ID
                const cradleId = cells[0].textContent.trim();
                
                // Ostatnia kolumna - State (sprawdzamy precyzyjnie w button .mj-button-txt)
                const stateCell = cells[cells.length - 1];
                const stateButton = stateCell.querySelector('button .mj-button-txt');
                const state = stateButton ? stateButton.textContent.trim().toLowerCase() : '';
                
                console.log(`[CradleScanner] Row ${i}: Cradle.ID=${cradleId}, State="${state}"`);
                
                // Pomijamy assety "Processing" - ktoś już nad nimi pracuje
                if (state.includes('processing')) {
                    console.log(`[CradleScanner] Skipping ${cradleId} - already processing`);
                    continue;
                }
                
                // Znaleziono pierwszy asset "Pending" (tabela jest posortowana według deadline)
                if (state.includes('pending')) {
                    const assetUrl = `https://cradle.egplusww.pl/assets/deliverable-details/${cradleId}/comments/`;
                    
                    console.log(`[CradleScanner] ✅ Found earliest pending asset: ${cradleId}`);
                    console.log(`[CradleScanner] Opening URL: ${assetUrl}`);
                    
                    this.status = `Opening asset ${cradleId}`;
                    this.showNotification(`✅ Opening pending asset ${cradleId}...`, 'success');
                    
                    // Otwórz w nowym oknie
                    window.open(assetUrl, '_blank');
                    
                    this.status = 'Ready';
                    return;
                }
            }
            
            // Nie znaleziono assetów Pending
            this.status = 'No pending assets found';
            this.showNotification('❌ No pending assets available for processing', 'warning');
            console.log('[CradleScanner] No pending assets found - all are either processing or completed');
            
        } catch (error) {
            console.error('[CradleScanner] Error finding pending asset:', error);
            this.status = `Error: ${error.message}`;
            this.showNotification(`❌ Error: ${error.message}`, 'error');
        }
    }
    
    async applyQAFilterOnly() {
        if (this.isScanning) {
            console.log('[CradleScanner] Already running...');
            return;
        }
        
        this.isScanning = true;
        
        try {
            console.log('[CradleScanner] === APPLYING QA FILTER ===');
            
            // KROK 1: Kliknij Saved States i wybierz QA FINAL PROOFREADING
            console.log('[CradleScanner] === STEP 1: Applying QA filter ===');
            await this.applyQAFilter();
            
            // KROK 2: Czekaj na zastosowanie filtra
            console.log('[CradleScanner] === STEP 2: Waiting for filter ===');
            await this.waitForFilter();
            
            this.status = 'Filter applied successfully';
            this.showNotification('QA FINAL PROOFREADING filter applied!', 'success');
            
        } catch (error) {
            console.error('[CradleScanner] ERROR:', error.message);
            this.status = `Error: ${error.message}`;
            this.showNotification(`Error: ${error.message}`, 'error');
        } finally {
            this.isScanning = false;
        }
    }
    
    async applyQAFilter() {
        this.status = 'Looking for Saved States button...';
        
        // Znajdź przycisk Saved States
        const savedStatesButton = this.findSavedStatesButton();
        
        if (!savedStatesButton) {
            throw new Error('Saved States button not found');
        }
        
        console.log('[CradleScanner] 🎯 Found Saved States button, clicking...');
        this.status = 'Clicking Saved States...';
        
        // Kliknij przycisk
        savedStatesButton.click();
        
        // Czekaj na otwarcie dropdown
        await this.wait(2000);
        
        // Znajdź opcję QA FINAL PROOFREADING
        const qaOption = this.findQAOption();
        
        if (!qaOption) {
            throw new Error('QA FINAL PROOFREADING option not found');
        }
        
        console.log('[CradleScanner] 🎯 Found QA FINAL PROOFREADING option, clicking...');
        this.status = 'Selecting QA FINAL PROOFREADING...';
        
        // Kliknij opcję QA
        qaOption.click();
        
        console.log('[CradleScanner] ✅ QA filter selected');
    }
    
    findSavedStatesButton() {
        console.log('[CradleScanner] Looking for Saved States button...');
        
        // Szukaj wszystkich przycisków
        const buttons = document.querySelectorAll('button');
        console.log('[CradleScanner] Found', buttons.length, 'buttons on page');
        
        for (const button of buttons) {
            const text = button.textContent.trim();
            
            if (text.includes('Saved States')) {
                console.log('[CradleScanner] ✅ Found Saved States button:', text);
                return button;
            }
        }
        
        console.log('[CradleScanner] ❌ Saved States button not found');
        return null;
    }
    
    findQAOption() {
        console.log('[CradleScanner] Looking for QA FINAL PROOFREADING option...');
        
        // Szukaj wszystkich widocznych elementów
        const allElements = document.querySelectorAll('*');
        console.log('[CradleScanner] Checking', allElements.length, 'elements for QA option');
        
        let foundElements = [];
        
        for (const element of allElements) {
            const text = element.textContent.trim();
            const isVisible = element.offsetParent !== null;
            
            if (text === 'QA FINAL PROOFREADING' && isVisible) {
                foundElements.push(element);
                console.log('[CradleScanner] ✅ Found QA FINAL PROOFREADING option:', element.tagName, element.className);
            }
        }
        
        if (foundElements.length > 0) {
            console.log('[CradleScanner] Using first QA option');
            return foundElements[0];
        }
        
        console.log('[CradleScanner] ❌ QA FINAL PROOFREADING option not found');
        return null;
    }
    
    async waitForFilter() {
        console.log('[CradleScanner] ⏳ Waiting 5 seconds for filter to apply...');
        this.status = 'Waiting for filter to apply...';
        
        await this.wait(5000);
        
        console.log('[CradleScanner] ✅ Filter wait completed');
    }
    
    async wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    stopAutomation() {
        this.isScanning = false;
        this.status = 'Stopped';
        console.log('[CradleScanner] Automation stopped');
    }
}

// Inicjalizacja
if (typeof window.cradleScanner === 'undefined') {
    window.cradleScanner = new CradleScanner();
}