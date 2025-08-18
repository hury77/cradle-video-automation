console.log('Video Compare loading...');

class VideoCompareAutomator {
  constructor() {
    console.log('VideoCompareAutomator ready');
  }
  
  compare(file1, file2) {
    console.log('Compare:', file1, file2);
  }
}

window.videoCompareAutomator = new VideoCompareAutomator();
console.log('Video Compare loaded successfully');