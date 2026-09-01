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

  handleMessage(message, sender, sendResponse) {
    console.log('Background received:', message.action);

    // Call async handler but don't await it here to allow return true
    (async () => {
      try {
        switch (message.action) {
          case 'DOWNLOAD_FILE':
            if (!message.url || !message.filename) {
               throw new Error('Missing url or filename');
            }
            const downloadId = await this.downloadFile(message.url, message.filename);
            sendResponse({ success: true, downloadId });
            break;

          case 'GET_STORAGE':
            const data = await chrome.storage.local.get(message.keys);
            sendResponse({ success: true, data });
            break;

          case 'SET_STORAGE':
            await chrome.storage.local.set(message.data);
            sendResponse({ success: true });
            break;

          case 'CHECK_DOWNLOAD_STATUS':
            chrome.downloads.search({ id: message.downloadId }, (results) => {
              if (chrome.runtime.lastError) {
                sendResponse({ success: false, error: chrome.runtime.lastError.message });
              } else if (results && results.length > 0) {
                const item = results[0];
                sendResponse({ 
                  success: true, 
                  state: item.state, 
                  bytesReceived: item.bytesReceived,
                  totalBytes: item.totalBytes,
                  error: item.error
                });
              } else {
                sendResponse({ success: false, error: 'Download not found' });
              }
            });
            return; // Return here because chrome.downloads.search is callback-based, sendResponse happens inside

          case 'RESUME_DOWNLOAD':
            chrome.downloads.resume(message.downloadId, () => {
              if (chrome.runtime.lastError) {
                sendResponse({ success: false, error: chrome.runtime.lastError.message });
              } else {
                sendResponse({ success: true });
              }
            });
            return; // Callback based

          default:
            sendResponse({ success: false, error: 'Unknown action' });
        }
      } catch (error) {
        console.error('Background error:', error);
        sendResponse({ success: false, error: error.message });
      }
    })();
    
    // Return true to indicate we will sendResponse asynchronously
    return true; 
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