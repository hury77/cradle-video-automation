console.log("Cradle Scanner background service worker loaded");

// Handle download requests from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Background received message:", request);
  
  if (request.action === 'DOWNLOAD_FILE') {
    handleDownload(request, sendResponse);
    return true; // Keep message channel open for async response
  }
});

async function handleDownload(request, sendResponse) {
  try {
    const { url, filename, type } = request;
    
    console.log(`🔽 Starting Chrome download: ${filename}`);
    console.log(`   URL: ${url}`);
    
    // Use Chrome Downloads API — respond immediately on start, not on completion.
    // Waiting for completion caused message channel timeouts for large video files.
    const downloadId = await chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: false,
      conflictAction: 'overwrite'
    });
    
    console.log(`✅ Chrome download started: ID ${downloadId}`);
    // Respond immediately — content script doesn't need to wait for completion
    sendResponse({ success: true, downloadId, filename, type });
    
  } catch (error) {
    console.error("❌ Download error:", error.message);
    sendResponse({ success: false, error: error.message, filename: request.filename, type: request.type });
  }
}

// Log extension lifecycle
chrome.runtime.onStartup.addListener(() => {
  console.log("Cradle Scanner extension started");
});

chrome.runtime.onInstalled.addListener(() => {
  console.log("Cradle Scanner extension installed/updated");
});