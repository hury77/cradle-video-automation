console.log("Cradle Scanner background service worker loaded");

// Handle download requests from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Background received message:", request);
  
  if (request.action === 'DOWNLOAD_FILE') {
    handleDownload(request, sendResponse);
    return true; // Keep message channel open for async response
  }
  
  if (request.action === 'LOG_TO_DASHBOARD') {
    handleDashboardLog(request.payload).then(() => sendResponse({success: true}));
    return true;
  }
});

async function handleDashboardLog(payload) {
  try {
    const response = await fetch("http://localhost:8001/api/v1/dashboard/logs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    console.log("Dashboard log sent:", response.status);
  } catch (error) {
    console.error("Dashboard log failed:", error);
  }
}

async function handleDownload(request, sendResponse) {
  try {
    const { url, filename, type } = request;
    
    console.log(`🔽 Starting Chrome download: ${filename}`);
    console.log(`   URL: ${url}`);
    console.log(`   Type: ${type}`);
    
    // Use Chrome Downloads API with cookies
    const downloadId = await chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false, // Don't show save dialog
      conflictAction: 'overwrite'
    });
    
    console.log(`✅ Chrome download started: ID ${downloadId}`);
    
    // Listen for download completion
    const downloadListener = (downloadDelta) => {
      if (downloadDelta.id === downloadId && downloadDelta.state) {
        if (downloadDelta.state.current === 'complete') {
          console.log(`✅ Download completed: ${filename}`);
          chrome.downloads.onChanged.removeListener(downloadListener);
          sendResponse({ 
            success: true, 
            downloadId: downloadId,
            filename: filename,
            type: type 
          });
        } else if (downloadDelta.state.current === 'interrupted') {
          console.error(`❌ Download failed: ${filename}`);
          chrome.downloads.onChanged.removeListener(downloadListener);
          sendResponse({ 
            success: false, 
            error: 'Download interrupted',
            filename: filename,
            type: type 
          });
        }
      }
    };
    
    chrome.downloads.onChanged.addListener(downloadListener);
    
    // Timeout after 2 minutes
    setTimeout(() => {
      chrome.downloads.onChanged.removeListener(downloadListener);
      sendResponse({ 
        success: false, 
        error: 'Download timeout',
        filename: filename,
        type: type 
      });
    }, 120000);
    
  } catch (error) {
    console.error("❌ Download error:", error);
    sendResponse({ 
      success: false, 
      error: error.message,
      filename: request.filename,
      type: request.type 
    });
  }
}

// Log extension lifecycle
chrome.runtime.onStartup.addListener(() => {
  console.log("Cradle Scanner extension started");
});

chrome.runtime.onInstalled.addListener(() => {
  console.log("Cradle Scanner extension installed/updated");
});