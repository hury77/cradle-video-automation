console.log('🔔 Notification Manager loading...');

class NotificationManager {
  constructor() {
    console.log('NotificationManager ready');
  }
  
  show(message) {
    console.log('📢 Notification:', message);
  }
}

window.notificationManager = new NotificationManager();
console.log('✅ Notification Manager loaded successfully');