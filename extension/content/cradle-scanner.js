console.log('🎬 Cradle Video Automation starting...');

// Notification Manager
class NotificationManager {
  constructor() {
    console.log('📢 NotificationManager ready');
  }
  
  show(message, type = 'info') {
    console.log(`📊 ${type.toUpperCase()}: ${message}`);
    this.showPageNotification(message, type);
  }
  
  showPageNotification(message, type) {
    const existing = document.getElementById('extension-notification');
    if (existing) existing.remove();
    
    const colors = {
      info: '#2196F3',
      success: '#4CAF50', 
      warning: '#FF9800',
      error: '#F44336'
    };
    
    const notification = document.createElement('div');
    notification.id = 'extension-notification';
    notification.style.cssText = `
      position: fixed; top: 20px; right: 20px; 
      background: ${colors[type] || colors.info}; color: white; 
      padding: 12px 16px; border-radius: 6px; 
      z-index: 99999; font-size: 14px; font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      max-width: 300px; word-wrap: break-word;
    `;
    notification.textContent = `🎯 ${message}`;
    
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 4000);
  }
}

// File Downloader  
class FileDownloader {
  constructor() {
    console.log('📁 FileDownloader ready');
  }
  
  async getAssetFiles() {
    console.log('🔍 Scanning for files...');
    notificationManager.show('Scanning for video files...', 'info');
    
    // Simulacja skanowania - później zaimplementujemy prawdziwe skanowanie DOM
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    notificationManager.show('Found video files!', 'success');
    return {
      acceptFile: { name: 'accept_file.mp4', path: '/downloads/accept.mp4' },
      emisyjnyFile: { name: 'emisyjny_file.mp4', path: '/downloads/emisyjny.mp4' }
    };
  }
}

// Video Compare Automator
class VideoCompareAutomator {
  constructor() {
    console.log('🎬 VideoCompareAutomator ready');
  }
  
  async startComparison(acceptFile, emisyjnyFile) {
    console.log('🎬 Starting video comparison...');
    notificationManager.show('Starting video comparison...', 'info');
    
    // Simulacja procesu porównania
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    notificationManager.show('Video comparison completed!', 'success');
    return { 
      status: 'completed', 
      acceptFile: acceptFile.name, 
      emisyjnyFile: emisyjnyFile.name,
      completedAt: new Date().toISOString()
    };
  }
}

// Main Scanner
class CradleScanner {
  constructor() {
    console.log('🎬 CradleScanner ready');
    this.isRunning = false;
  }
  
  async startAutomation() {
    if (this.isRunning) {
      notificationManager.show('Automation already running!', 'warning');
      return;
    }
    
    this.isRunning = true;
    notificationManager.show('Starting Cradle automation...', 'info');
    console.log('🚀 Starting automation workflow...');
    
    try {
      // Step 1: Get files
      console.log('📁 Step 1: Getting asset files...');
      const files = await fileDownloader.getAssetFiles();
      console.log('📁 Files found:', files);
      
      // Step 2: Start video comparison
      console.log('🎬 Step 2: Starting video comparison...');
      const result = await videoCompareAutomator.startComparison(
        files.acceptFile, 
        files.emisyjnyFile
      );
      console.log('🎬 Comparison result:', result);
      
      // Success
      notificationManager.show('✅ Automation completed successfully!', 'success');
      console.log('🎉 Automation workflow completed:', result);
      
      return result;
      
    } catch (error) {
      notificationManager.show(`❌ Automation failed: ${error.message}`, 'error');
      console.error('💥 Automation error:', error);
      throw error;
    } finally {
      this.isRunning = false;
      console.log('🏁 Automation workflow finished');
    }
  }
  
  getStatus() {
    return {
      isRunning: this.isRunning,
      components: {
        notificationManager: !!notificationManager,
        fileDownloader: !!fileDownloader,
        videoCompareAutomator: !!videoCompareAutomator
      }
    };
  }
}

// Initialize all components
const notificationManager = new NotificationManager();
const fileDownloader = new FileDownloader(); 
const videoCompareAutomator = new VideoCompareAutomator();
const cradleScanner = new CradleScanner();

// Listen for commands from popup or external
document.addEventListener('extension-command', (event) => {
  const { action, data } = event.detail;
  console.log('📨 Received command:', action);
  
  switch (action) {
    case 'START_AUTOMATION':
      cradleScanner.startAutomation();
      break;
      
    case 'STOP_AUTOMATION':
      if (cradleScanner.isRunning) {
        notificationManager.show('Stopping automation...', 'warning');
        cradleScanner.isRunning = false;
      }
      break;
      
    case 'GET_STATUS':
      const status = cradleScanner.getStatus();
      console.log('📊 Extension Status:', status);
      notificationManager.show(`Status: ${status.isRunning ? 'Running' : 'Ready'}`, 'info');
      break;
      
    case 'SHOW_NOTIFICATION':
      notificationManager.show(data.message, data.type);
      break;
  }
});

// Ready notification
notificationManager.show('🚀 Cradle Video Automation Ready!', 'success');
console.log('🚀 All components loaded and ready for automation!');