// Popup script for Manifest V3
class PopupController {
  constructor() {
    this.isRunning = false;
    this.init();
  }

  init() {
    console.log('Popup initializing...');
    
    // Get DOM elements
    this.startBtn = document.getElementById('startBtn');
    this.stopBtn = document.getElementById('stopBtn');
    this.statusBtn = document.getElementById('statusBtn');
    this.statusDiv = document.getElementById('status');
    this.logDiv = document.getElementById('log');

    // Bind event listeners
    this.startBtn.addEventListener('click', () => this.startAutomation());
    this.stopBtn.addEventListener('click', () => this.stopAutomation());
    this.statusBtn.addEventListener('click', () => this.checkStatus());

    // Check initial status
    this.checkStatus();
    
    console.log('Popup initialized');
  }

  async sendCommandToContentScript(action, data = {}) {
    try {
      // Get active tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab || !tab.url.includes('cradle.egplusww.pl')) {
        throw new Error('Please navigate to Cradle first');
      }

      // Use Manifest V3 API
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (action, data) => {
          document.dispatchEvent(new CustomEvent('extension-command', {
            detail: { action: action, data: data }
          }));
        },
        args: [action, data]
      });

      this.log(`✅ Command sent: ${action}`);
      return { success: true };

    } catch (error) {
      console.error('Failed to send command:', error);
      this.log(`❌ Error: ${error.message}`, 'error');
      throw error;
    }
  }

  async startAutomation() {
    try {
      this.log('🚀 Starting automation...');
      this.updateUI(true);
      
      await this.sendCommandToContentScript('START_AUTOMATION');
      
      // Monitor automation
      this.monitorAutomation();
      
    } catch (error) {
      this.log(`❌ Failed to start: ${error.message}`, 'error');
      this.updateUI(false);
    }
  }

  async stopAutomation() {
    try {
      this.log('⏹️ Stopping automation...');
      
      await this.sendCommandToContentScript('STOP_AUTOMATION');
      this.updateUI(false);
      
    } catch (error) {
      this.log(`❌ Failed to stop: ${error.message}`, 'error');
    }
  }

  async checkStatus() {
    try {
      await this.sendCommandToContentScript('GET_STATUS');
      this.log('📊 Status check requested');
    } catch (error) {
      this.log(`❌ Status check failed: ${error.message}`, 'error');
    }
  }

  monitorAutomation() {
    if (!this.isRunning) return;
    
    setTimeout(() => {
      if (this.isRunning) {
        this.checkStatus();
        this.monitorAutomation();
      }
    }, 3000);
  }

  updateUI(running) {
    this.isRunning = running;
    
    if (running) {
      this.startBtn.disabled = true;
      this.stopBtn.disabled = false;
      this.statusDiv.textContent = 'Running...';
      this.statusDiv.className = 'status running';
    } else {
      this.startBtn.disabled = false;
      this.stopBtn.disabled = true;
      this.statusDiv.textContent = 'Ready';
      this.statusDiv.className = 'status';
    }
  }

  log(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${message}\n`;
    
    // Add to log
    this.logDiv.textContent = logEntry + this.logDiv.textContent;
    
    // Keep only last 15 entries
    const lines = this.logDiv.textContent.split('\n');
    if (lines.length > 20) {
      this.logDiv.textContent = lines.slice(0, 20).join('\n');
    }
    
    console.log(`Popup: ${message}`);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new PopupController();
});