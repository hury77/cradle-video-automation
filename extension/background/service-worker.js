console.log("Cradle Scanner background service worker loaded");

// Handle download requests from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Background received message:", request);
  
  if (request.action === 'DOWNLOAD_FILE') {
    handleDownload(request, sendResponse);
    return true; // Keep message channel open for async response
  }
  
  if (request.action === 'CHECK_DOWNLOAD_STATUS') {
    checkDownloadStatus(request, sendResponse);
    return true;
  }
  
  if (request.action === 'RESUME_DOWNLOAD') {
    resumeDownload(request, sendResponse);
    return true;
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
    
    const downloadId = await chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false,
      conflictAction: 'overwrite'
    });
    
    console.log(`✅ Chrome download started: ID ${downloadId}`);
    
    // Zamiast czekać do końca z limitem czasowym, odpowiadamy natychmiast z downloadId
    sendResponse({ 
      success: true, 
      downloadId: downloadId,
      filename: filename,
      type: type,
      status: "started"
    });
    
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

async function checkDownloadStatus(request, sendResponse) {
  try {
    const results = await chrome.downloads.search({ id: request.downloadId });
    if (results && results.length > 0) {
      const item = results[0];
      console.log(`📊 Status for ${request.downloadId}: state=${item.state}, bytes=${item.bytesReceived}/${item.totalBytes}`);
      sendResponse({ success: true, state: item.state, error: item.error, bytesReceived: item.bytesReceived, totalBytes: item.totalBytes });
    } else {
      sendResponse({ success: false, error: 'Download ID not found' });
    }
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

async function resumeDownload(request, sendResponse) {
  try {
    console.log(`🔄 Attempting to resume download ID: ${request.downloadId}`);
    await chrome.downloads.resume(request.downloadId);
    sendResponse({ success: true });
  } catch (error) {
    console.error(`❌ Resume failed:`, error);
    sendResponse({ success: false, error: error.message });
  }
}

// Log extension lifecycle
chrome.runtime.onStartup.addListener(() => {
  console.log("Cradle Scanner extension started");
});

chrome.runtime.onInstalled.addListener(() => {
  console.log("Cradle Scanner extension installed/updated");
});
