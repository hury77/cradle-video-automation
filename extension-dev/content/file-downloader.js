console.log('File Downloader loading...');

class FileDownloader {
  constructor() {
    console.log('FileDownloader ready');
  }
  
  download(url) {
    console.log('Download:', url);
  }
}

window.fileDownloader = new FileDownloader();
console.log('File Downloader loaded successfully');