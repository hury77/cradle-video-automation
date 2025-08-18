// background.js - Minimal Service Worker
class BackgroundService {
  constructor() {
    this.init();
  }

  init() {
    console.log('Background service starting...');
    
    // Install/update handler
    chrome.runtime.onInstalled.addListener((details) => {
      console.log('Extension event:', details.reason);
    });

    // Message handler  
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message, sender, sendResponse);
      return true;
    });

    console.log('Background service initialized');
  }

  async handleMessage(message, sender, sendResponse) {
    try {
      console.log('Background received:', message.action);
      
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

        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    } catch (error) {
      console.error('Background error:', error);
      sendResponse({ success: false, error: error.message });
    }
  }

  async downloadFile(url, filename) {
    try {
      return new Promise((resolve, reject) => {
        chrome.downloads.download({
          url: url,
          filename: filename,
          conflictAction: 'uniquify'
        }, (downloadId) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            console.log('Download started:', downloadId);
            resolve(downloadId);
          }
        });
      });
    } catch (error) {
      console.error('Download failed:', error);
      throw error;
    }
  }
}

// Initialize
new BackgroundService();