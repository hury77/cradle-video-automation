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