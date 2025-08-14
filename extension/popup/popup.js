// popup.js - Main UI controller
class AutomationController {
  constructor() {
    this.isRunning = false;
    this.maxTasks = 5;
    this.autoMode = false;
    this.init();
  }

  init() {
    this.loadSettings();
    this.bindEvents();
    this.updateUI();
    this.loadActivityLog();
  }

  bindEvents() {
    // Main buttons
    document.getElementById('scan-btn').addEventListener('click', () => {
      this.startAutomation();
    });

    document.getElementById('stop-btn').addEventListener('click', () => {
      this.stopAutomation();
    });

    // Settings
    document.getElementById('auto-mode').addEventListener('change', (e) => {
      this.autoMode = e.target.checked;
      this.saveSettings();
    });

    document.getElementById('max-tasks').addEventListener('change', (e) => {
      this.maxTasks = parseInt(e.target.value);
      this.saveSettings();
    });

    // Listen for messages from content scripts
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message);
    });
  }

  async startAutomation() {
    if (this.isRunning) return;

    this.isRunning = true;
    this.updateUI();
    this.logActivity('🚀 Starting automation...', 'info');

    try {
      // Send message to content script to start scanning
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!this.isCradleTab(tab.url)) {
        this.logActivity('❌ Please navigate to Cradle first', 'error');
        this.updateStatus('Please open Cradle in current tab', 'error');
        this.isRunning = false;
        this.updateUI();
        return;
      }

      await chrome.tabs.sendMessage(tab.id, {
        action: 'START_AUTOMATION',
        maxTasks: this.maxTasks
      });

      this.updateStatus('🔍 Scanning for pending tasks...', 'processing');

    } catch (error) {
      this.logActivity(`❌ Error: ${error.message}`, 'error');
      this.updateStatus('Error starting automation', 'error');
      this.isRunning = false;
      this.updateUI();
    }
  }

  async stopAutomation() {
    if (!this.isRunning) return;

    this.isRunning = false;
    this.updateUI();
    this.logActivity('⏹️ Stopping automation...', 'warning');

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      await chrome.tabs.sendMessage(tab.id, { action: 'STOP_AUTOMATION' });
      this.updateStatus('Automation stopped', 'info');
    } catch (error) {
      console.log('Error stopping automation:', error);
    }
  }

  handleMessage(message) {
    switch (message.type) {
      case 'STATUS_UPDATE':
        this.updateStatus(message.status, message.statusType);
        break;
      case 'PROGRESS_UPDATE':
        this.updateProgress(message.current, message.total, message.message);
        break;
      case 'LOG_ACTIVITY':
        this.logActivity(message.message, message.logType);
        break;
      case 'AUTOMATION_COMPLETE':
        this.onAutomationComplete(message.results);
        break;
      case 'AUTOMATION_ERROR':
        this.onAutomationError(message.error);
        break;
    }
  }

  updateStatus(message, type = 'info') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
  }

  updateProgress(current, total, message) {
    const progressEl = document.getElementById('progress');
    const progressFill = progressEl.querySelector('.progress-fill');
    const progressText = progressEl.querySelector('.progress-text');

    if (total > 0) {
      progressEl.classList.remove('hidden');
      const percentage = (current / total) * 100;
      progressFill.style.width = `${percentage}%`;
      progressText.textContent = `${message} (${current}/${total})`;
    } else {
      progressEl.classList.add('hidden');
    }
  }

  logActivity(message, type = 'info') {
    const logContainer = document.getElementById('activity-log');
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    
    const timestamp = new Date().toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit' 
    });

    logEntry.innerHTML = `
      <span class="timestamp">${timestamp}</span>
      <span class="message">${message}</span>
    `;

    logContainer.insertBefore(logEntry, logContainer.firstChild);

    // Keep only last 50 entries
    while (logContainer.children.length > 50) {
      logContainer.removeChild(logContainer.lastChild);
    }

    // Save to storage
    this.saveActivityLog();
  }

  onAutomationComplete(results) {
    this.isRunning = false;
    this.updateUI();
    this.updateProgress(0, 0, '');
    
    const message = `✅ Completed! Processed ${results.processed} assets, ${results.comparisons} comparisons ready`;
    this.updateStatus(message, 'success');
    this.logActivity(message, 'success');

    // Show notification
    chrome.notifications.create({
      type: 'basic',
      iconUrl: '/assets/icons/icon48.png',
      title: 'Cradle Automation Complete',
      message: `${results.comparisons} video comparisons are ready for review!`
    });
  }

  onAutomationError(error) {
    this.isRunning = false;
    this.updateUI();
    this.updateProgress(0, 0, '');
    this.updateStatus(`❌ Error: ${error}`, 'error');
    this.logActivity(`❌ Error: ${error}`, 'error');
  }

  updateUI() {
    const scanBtn = document.getElementById('scan-btn');
    const stopBtn = document.getElementById('stop-btn');

    if (this.isRunning) {
      scanBtn.classList.add('hidden');
      stopBtn.classList.remove('hidden');
    } else {
      scanBtn.classList.remove('hidden');
      stopBtn.classList.add('hidden');
    }
  }

  isCradleTab(url) {
    return url && (url.includes('cradle.com') || url.includes('omnipro.global'));
  }

  saveSettings() {
    chrome.storage.local.set({
      autoMode: this.autoMode,
      maxTasks: this.maxTasks
    });
  }

  loadSettings() {
    chrome.storage.local.get(['autoMode', 'maxTasks'], (result) => {
      this.autoMode = result.autoMode || false;
      this.maxTasks = result.maxTasks || 5;

      document.getElementById('auto-mode').checked = this.autoMode;
      document.getElementById('max-tasks').value = this.maxTasks;
    });
  }

  saveActivityLog() {
    const logEntries = Array.from(document.querySelectorAll('.log-entry')).slice(0, 20).map(entry => ({
      timestamp: entry.querySelector('.timestamp').textContent,
      message: entry.querySelector('.message').textContent,
      type: entry.className.split(' ').find(cls => ['info', 'success', 'error', 'warning'].includes(cls)) || 'info'
    }));

    chrome.storage.local.set({ activityLog: logEntries });
  }

  loadActivityLog() {
    chrome.storage.local.get(['activityLog'], (result) => {
      if (result.activityLog) {
        const logContainer = document.getElementById('activity-log');
        logContainer.innerHTML = '';

        result.activityLog.forEach(entry => {
          const logEntry = document.createElement('div');
          logEntry.className = `log-entry ${entry.type}`;
          logEntry.innerHTML = `
            <span class="timestamp">${entry.timestamp}</span>
            <span class="message">${entry.message}</span>
          `;
          logContainer.appendChild(logEntry);
        });
      }
    });
  }
}

// Initialize when popup loads
document.addEventListener('DOMContentLoaded', () => {
  new AutomationController();
});