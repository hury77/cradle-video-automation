// background.js - Service Worker
class BackgroundService {
  constructor() {
    this.init();
  }

  init() {
    // Install/update handler
    chrome.runtime.onInstalled.addListener((details) => {
      if (details.reason === 'install') {
        console.log('Cradle Video Automation installed');
        this.showWelcomeNotification();
      } else if (details.reason === 'update') {
        console.log('Cradle Video Automation updated');
      }
    });

    // Message handler
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message, sender, sendResponse);
      return true; // Keep channel open for async response
    });

    // Tab update handler
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (changeInfo.status === 'complete' && this.isCradleTab(tab.url)) {
        // Inject content scripts if needed
        this.ensureContentScriptsLoaded(tabId);
      }
    });
  }

  async handleMessage(message, sender, sendResponse) {
    try {
      switch (message.action) {
        case 'DOWNLOAD_FILE':
          await this.downloadFile(message.url, message.filename);
          sendResponse({ success: true });
          break;

        case 'GET_STORAGE':
          const data = await chrome.storage.local.get(message.keys);
          sendResponse({ success: true, data });
          break;

        case 'SET_STORAGE':
          await chrome.storage.local.set(message.data);
          sendResponse({ success: true });
          break;

        case 'SHOW_NOTIFICATION':
          await this.showNotification(message.options);
          sendResponse({ success: true });
          break;

        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    } catch (error) {
      console.error('Background service error:', error);
      sendResponse({ success: false, error: error.message });
    }
  }

  async downloadFile(url, filename) {
    return new Promise((resolve, reject) => {
      chrome.downloads.download({
        url: url,
        filename: filename,
        conflictAction: 'uniquify'
      }, (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(downloadId);
        }
      });
    });
  }

  async showNotification(options) {
    return chrome.notifications.create({
      type: 'basic',
      iconUrl: '/assets/icons/icon48.png',
      title: 'Cradle Video Automation',
      ...options
    });
  }

  showWelcomeNotification() {
    this.showNotification({
      title: 'Welcome to Cradle Video Automation!',
      message: 'Extension installed successfully. Navigate to Cradle to get started.'
    });
  }

  isCradleTab(url) {
    return url && (url.includes('cradle.com') || url.includes('omnipro.global'));
  }

  async ensureContentScriptsLoaded(tabId) {
    try {
      // Check if content script is already loaded
      const response = await chrome.tabs.sendMessage(tabId, { action: 'PING' });
      if (response && response.pong) {
        return; // Already loaded
      }
    } catch (error) {
      // Content script not loaded, inject it
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tabId },
          files: [
            'content/cradle-scanner.js',
            'content/file-downloader.js',
            'content/video-compare.js',
            'content/notification.js'
          ]
        });
        console.log('Content scripts injected into tab:', tabId);
      } catch (injectError) {
        console.error('Failed to inject content scripts:', injectError);
      }
    }
  }
}

// Initialize background service
new BackgroundService();