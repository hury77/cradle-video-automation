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
    this.findBtn = document.getElementById('findBtn');
    this.takeBtn = document.getElementById('takeBtn');
    this.statusBtn = document.getElementById('statusBtn');
    this.statusDiv = document.getElementById('status');
    this.logDiv = document.getElementById('log');

    // Bind event listeners
    this.startBtn.addEventListener('click', () => this.startAutomation());
    this.stopBtn.addEventListener('click', () => this.stopAutomation());
    this.findBtn.addEventListener('click', () => this.findAsset());
    this.takeBtn.addEventListener('click', () => this.takeAsset());
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

  async findAsset() {
    try {
      this.log('🔍 Finding pending asset...');
      await this.sendCommandToContentScript('FIND_ASSET');
    } catch (error) {
      this.log(`❌ Find asset failed: ${error.message}`, 'error');
    }
  }

  async takeAsset() {
    try {
      this.log('✋ Taking asset...');
      await this.sendCommandToContentScript('TAKE_ASSET');
    } catch (error) {
      this.log(`❌ Take asset failed: ${error.message}`, 'error');
    }
  }

  async checkStatus() {
    try {
      await this.sendCommandToContentScript('GET_STATUS');
    } catch (error) {
      this.log(`❌ Status check failed: ${error.message}`, 'error');
    }
  }

  monitorAutomation() {
    // This could be enhanced to listen for status updates
    setTimeout(() => {
      if (this.isRunning) {
        this.checkStatus();
        this.monitorAutomation();
      }
    }, 2000);
  }

  updateUI(running) {
    this.isRunning = running;
    
    if (running) {
      this.startBtn.style.display = 'none';
      this.stopBtn.style.display = 'block';
      this.statusDiv.textContent = '🔄 Running...';
      this.statusDiv.className = 'status running';
    } else {
      this.startBtn.style.display = 'block';
      this.stopBtn.style.display = 'none';
      this.statusDiv.textContent = '⏹️ Stopped';
      this.statusDiv.className = 'status stopped';
    }
  }

  log(message, type = 'info') {
    console.log(message);
    
    if (this.logDiv) {
      const logEntry = document.createElement('div');
      logEntry.className = `log-entry ${type}`;
      logEntry.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
      
      this.logDiv.appendChild(logEntry);
      this.logDiv.scrollTop = this.logDiv.scrollHeight;
      
      // Keep only last 10 entries
      while (this.logDiv.children.length > 10) {
        this.logDiv.removeChild(this.logDiv.firstChild);
      }
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new PopupController();
});