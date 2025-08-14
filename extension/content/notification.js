// notification.js - Handles communication with popup and notifications
class NotificationManager {
  constructor() {
    this.init();
  }

  init() {
    console.log('📢 Notification Manager initialized');
  }

  // Status updates for popup
  sendStatus(message, type = 'info') {
    this.sendMessageToPopup({
      type: 'STATUS_UPDATE',
      status: message,
      statusType: type
    });
    console.log(`📊 Status [${type}]: ${message}`);
  }

  // Progress updates for popup
  sendProgress(current, total, message = '') {
    this.sendMessageToPopup({
      type: 'PROGRESS_UPDATE',
      current: current,
      total: total,
      message: message
    });
    console.log(`📈 Progress: ${current}/${total} - ${message}`);
  }

  // Activity log entries for popup
  logActivity(message, logType = 'info') {
    this.sendMessageToPopup({
      type: 'LOG_ACTIVITY',
      message: message,
      logType: logType
    });
    
    // Also log to console with appropriate level
    switch (logType) {
      case 'error':
        console.error(`📝 ${message}`);
        break;
      case 'warning':
        console.warn(`📝 ${message}`);
        break;
      case 'success':
        console.log(`📝 ✅ ${message}`);
        break;
      default:
        console.log(`📝 ${message}`);
    }
  }

  // Automation completion notification
  sendAutomationComplete(results) {
    this.sendMessageToPopup({
      type: 'AUTOMATION_COMPLETE',
      results: results
    });
    
    // Send browser notification
    this.sendBrowserNotification({
      title: 'Cradle Automation Complete! 🎉',
      message: `Processed ${results.processed} assets. ${results.comparisons} comparisons ready for review!`,
      type: 'success'
    });
    
    console.log('🎉 Automation completed:', results);
  }

  // Automation error notification
  sendAutomationError(error) {
    this.sendMessageToPopup({
      type: 'AUTOMATION_ERROR',
      error: error
    });
    
    // Send browser notification
    this.sendBrowserNotification({
      title: 'Cradle Automation Error ❌',
      message: `Automation failed: ${error}`,
      type: 'error'
    });
    
    console.error('💥 Automation error:', error);
  }

  // Asset processing notifications
  sendAssetStarted(assetName) {
    this.logActivity(`🔄 Started processing: ${assetName}`, 'info');
  }

  sendAssetCompleted(assetName) {
    this.logActivity(`✅ Completed: ${assetName}`, 'success');
  }

  sendAssetError(assetName, error) {
    this.logActivity(`❌ Error processing ${assetName}: ${error}`, 'error');
  }

  // File operation notifications
  sendFileDownloadStarted(filename) {
    this.logActivity(`⬇️ Downloading: ${filename}`, 'info');
  }

  sendFileDownloadCompleted(filename) {
    this.logActivity(`📁 Downloaded: ${filename}`, 'success');
  }

  sendFileDownloadError(filename, error) {
    this.logActivity(`❌ Download failed for ${filename}: ${error}`, 'error');
  }

  // Video Compare notifications
  sendVideoCompareStarted(acceptFile, emisyjnyFile) {
    this.logActivity(`🎬 Starting comparison: ${acceptFile} vs ${emisyjnyFile}`, 'info');
  }

  sendVideoCompareCompleted() {
    this.logActivity(`✅ Video comparison completed!`, 'success');
  }

  sendVideoCompareError(error) {
    this.logActivity(`❌ Video comparison failed: ${error}`, 'error');
  }

  // Navigation notifications
  sendNavigationStarted(destination) {
    this.logActivity(`🧭 Navigating to: ${destination}`, 'info');
  }

  sendNavigationCompleted(destination) {
    this.logActivity(`📍 Reached: ${destination}`, 'info');
  }

  sendNavigationError(destination, error) {
    this.logActivity(`❌ Navigation failed to ${destination}: ${error}`, 'error');
  }

  // Task management notifications
  sendTaskFound(count) {
    this.logActivity(`📋 Found ${count} pending tasks`, 'info');
  }

  sendTaskTaken(taskName) {
    this.logActivity(`✋ Took task: ${taskName}`, 'info');
  }

  sendTaskSkipped(taskName, reason) {
    this.logActivity(`⏭️ Skipped ${taskName}: ${reason}`, 'warning');
  }

  // System notifications
  sendSystemInfo(message) {
    this.logActivity(`ℹ️ ${message}`, 'info');
  }

  sendSystemWarning(message) {
    this.logActivity(`⚠️ ${message}`, 'warning');
  }

  sendSystemError(message) {
    this.logActivity(`💥 ${message}`, 'error');
  }

  // Debug notifications (only in development)
  sendDebug(message, data = null) {
    if (this.isDebugMode()) {
      const debugMessage = data ? `${message} | Data: ${JSON.stringify(data, null, 2)}` : message;
      this.logActivity(`🐛 Debug: ${debugMessage}`, 'info');
      console.log('🐛 Debug:', message, data);
    }
  }

  // Send message to popup
  sendMessageToPopup(message) {
    try {
      chrome.runtime.sendMessage(message).catch(error => {
        // Popup might not be open, that's ok
        if (!error.message.includes('Receiving end does not exist')) {
          console.warn('Failed to send message to popup:', error);
        }
      });
    } catch (error) {
      console.warn('Failed to send message to popup:', error);
    }
  }

  // Send browser notification via background script
  sendBrowserNotification(options) {
    try {
      chrome.runtime.sendMessage({
        action: 'SHOW_NOTIFICATION',
        options: {
          title: options.title,
          message: options.message,
          iconUrl: this.getNotificationIcon(options.type)
        }
      }).catch(error => {
        console.warn('Failed to send browser notification:', error);
      });
    } catch (error) {
      console.warn('Failed to send browser notification:', error);
    }
  }

  // Show in-page notification overlay
  showPageNotification(message, type = 'info', duration = 5000) {
    // Remove any existing notification
    const existing = document.getElementById('cradle-automation-notification');
    if (existing) {
      existing.remove();
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.id = 'cradle-automation-notification';
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      max-width: 300px;
      padding: 16px 20px;
      border-radius: 8px;
      color: white;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      font-weight: 500;
      z-index: 10000;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      animation: slideInRight 0.3s ease-out;
      cursor: pointer;
    `;

    // Set background color based on type
    const colors = {
      info: '#2196F3',
      success: '#4CAF50', 
      warning: '#FF9800',
      error: '#F44336',
      processing: '#9C27B0'
    };
    notification.style.backgroundColor = colors[type] || colors.info;

    // Add icon based on type
    const icons = {
      info: 'ℹ️',
      success: '✅',
      warning: '⚠️', 
      error: '❌',
      processing: '⏳'
    };
    const icon = icons[type] || icons.info;

    notification.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 16px;">${icon}</span>
        <span>${message}</span>
      </div>
    `;

    // Add slide-in animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);

    // Add to page
    document.body.appendChild(notification);

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        if (notification.parentElement) {
          notification.style.animation = 'slideInRight 0.3s ease-out reverse';
          setTimeout(() => {
            if (notification.parentElement) {
              notification.remove();
            }
          }, 300);
        }
      }, duration);
    }

    // Remove on click
    notification.addEventListener('click', () => {
      if (notification.parentElement) {
        notification.remove();
      }
    });

    return notification;
  }

  // Utility methods
  getNotificationIcon(type) {
    const icons = {
      success: '/assets/icons/icon48.png',
      error: '/assets/icons/icon48.png',
      warning: '/assets/icons/icon48.png',
      info: '/assets/icons/icon48.png'
    };
    return icons[type] || icons.info;
  }

  isDebugMode() {
    // Check if we're in debug mode (could be based on storage, URL params, etc.)
    return window.location.search.includes('debug=true') || 
           localStorage.getItem('cradle-automation-debug') === 'true';
  }

  // Batch notifications for better performance
  batchNotifications(notifications, delay = 100) {
    notifications.forEach((notification, index) => {
      setTimeout(() => {
        this.logActivity(notification.message, notification.type);
      }, index * delay);
    });
  }

  // Format time for notifications
  formatTime(date = new Date()) {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  // Format duration
  formatDuration(startTime, endTime = new Date()) {
    const duration = endTime - startTime;
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  }
}

// Initialize notification manager
if (!window.notificationManager) {
  window.notificationManager = new NotificationManager();
}