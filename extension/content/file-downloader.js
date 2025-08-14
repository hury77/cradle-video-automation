// file-downloader.js - Handles file discovery and downloading from various sources
class FileDownloader {
  constructor() {
    this.downloadDir = 'cradle-automation-downloads';
    
    // File sections to check (in priority order)
    this.sections = [
      'QC_final',
      'QA Proofreading', 
      'PM Approval',
      'Broadcast file preparation',
      'Final file preparation',
      'Master',
      'Emisyjny',
      'QA final proofreading'
    ];

    // Supported video file extensions
    this.videoExtensions = ['.mp4', '.mov', '.mxf', '.avi', '.mkv', '.wmv'];
    this.archiveExtensions = ['.zip', '.rar', '.7z'];
    
    this.init();
  }

  init() {
    console.log('📁 File Downloader initialized');
  }

  async getAssetFiles() {
    try {
      console.log('🔍 Searching for asset files...');
      
      // Parse the current asset page
      const workflowSteps = await this.parseWorkflowSteps();
      
      // Find accept file (from QA proofreading or QC_final)
      const acceptFile = await this.findAcceptFile(workflowSteps);
      
      // Find emisyjny file (from QA final proofreading - latest attachment)
      const emisyjnyFile = await this.findEmisyjnyFile(workflowSteps);
      
      // If no direct attachments, try network paths and LucidLink
      const alternativeFiles = await this.findAlternativeFiles(acceptFile, emisyjnyFile);
      
      const result = {
        acceptFile: acceptFile || alternativeFiles.acceptFile,
        emisyjnyFile: emisyjnyFile || alternativeFiles.emisyjnyFile
      };

      console.log('📁 File search results:', result);
      return result;

    } catch (error) {
      console.error('Error getting asset files:', error);
      throw new Error(`Failed to get asset files: ${error.message}`);
    }
  }

  async parseWorkflowSteps() {
    // Look for workflow steps table or sections
    const workflowSteps = {};

    // Method 1: Table-based workflow
    const tables = document.querySelectorAll('table');
    for (const table of tables) {
      const rows = table.querySelectorAll('tr');
      
      for (const row of rows) {
        const cells = row.querySelectorAll('td, th');
        if (cells.length >= 2) {
          const stepName = cells[0].textContent.trim();
          const stepContent = cells[1];
          
          // Check if this is a workflow step we care about
          for (const section of this.sections) {
            if (this.matchesSection(stepName, section)) {
              workflowSteps[section] = {
                element: stepContent,
                name: stepName,
                files: await this.findFilesInElement(stepContent)
              };
              break;
            }
          }
        }
      }
    }

    // Method 2: Section-based workflow (divs, sections)
    for (const section of this.sections) {
      if (!workflowSteps[section]) {
        const sectionElement = await this.findSectionElement(section);
        if (sectionElement) {
          workflowSteps[section] = {
            element: sectionElement,
            name: section,
            files: await this.findFilesInElement(sectionElement)
          };
        }
      }
    }

    console.log('📋 Parsed workflow steps:', Object.keys(workflowSteps));
    return workflowSteps;
  }

  async findAcceptFile(workflowSteps) {
    // Look for accept file in QA proofreading or QC_final steps
    const acceptSections = ['QA Proofreading', 'QC_final'];
    
    for (const section of acceptSections) {
      if (workflowSteps[section] && workflowSteps[section].files.length > 0) {
        // Get the latest/last file from this section
        const files = workflowSteps[section].files;
        const videoFile = files.find(f => this.isVideoFile(f.name)) || files[files.length - 1];
        
        if (videoFile) {
          console.log(`📄 Found accept file in ${section}:`, videoFile.name);
          return await this.downloadFile(videoFile, `accept_${videoFile.name}`);
        }
      }
    }

    console.log('⚠️ No accept file found in standard sections');
    return null;
  }

  async findEmisyjnyFile(workflowSteps) {
    // Look for emisyjny file in QA final proofreading step (latest attachment)
    const emisyjnySections = ['QA final proofreading', 'Emisyjny'];
    
    for (const section of emisyjnySections) {
      if (workflowSteps[section] && workflowSteps[section].files.length > 0) {
        // Get the latest/last file from this section
        const files = workflowSteps[section].files;
        const videoFile = files.find(f => this.isVideoFile(f.name)) || files[files.length - 1];
        
        if (videoFile) {
          console.log(`📄 Found emisyjny file in ${section}:`, videoFile.name);
          return await this.downloadFile(videoFile, `emisyjny_${videoFile.name}`);
        }
      }
    }

    console.log('⚠️ No emisyjny file found in standard sections');
    return null;
  }

  async findAlternativeFiles(existingAcceptFile, existingEmisyjnyFile) {
    const result = {
      acceptFile: existingAcceptFile,
      emisyjnyFile: existingEmisyjnyFile
    };

    // If we have accept file, we can derive prefix for network search
    let filePrefix = null;
    if (existingAcceptFile) {
      filePrefix = this.extractFilePrefix(existingAcceptFile.name);
    }

    // Method 1: Network paths (/Volumes/)
    if (!result.emisyjnyFile || !result.acceptFile) {
      const networkFiles = await this.searchNetworkPaths(filePrefix);
      if (networkFiles.acceptFile && !result.acceptFile) {
        result.acceptFile = networkFiles.acceptFile;
      }
      if (networkFiles.emisyjnyFile && !result.emisyjnyFile) {
        result.emisyjnyFile = networkFiles.emisyjnyFile;
      }
    }

    // Method 2: LucidLink
    if (!result.emisyjnyFile || !result.acceptFile) {
      const lucidFiles = await this.searchLucidLink(filePrefix);
      if (lucidFiles.acceptFile && !result.acceptFile) {
        result.acceptFile = lucidFiles.acceptFile;
      }
      if (lucidFiles.emisyjnyFile && !result.emisyjnyFile) {
        result.emisyjnyFile = lucidFiles.emisyjnyFile;
      }
    }

    return result;
  }

  async searchNetworkPaths(filePrefix) {
    const result = { acceptFile: null, emisyjnyFile: null };

    try {
      // Look for network path references on the page
      const pathElements = document.querySelectorAll('p, div, span');
      
      for (const element of pathElements) {
        const text = element.textContent.trim();
        if (text.startsWith('/Volumes/')) {
          console.log('🔗 Found network path:', text);
          
          // This would require native messaging or different approach
          // For now, log the path for manual verification
          console.log('📂 Network path found but requires native file access:', text);
          
          // In a real implementation, you'd need:
          // 1. Native messaging host to access local files
          // 2. Or user to manually copy files to accessible location
          break;
        }
      }
    } catch (error) {
      console.log('Network path search failed:', error);
    }

    return result;
  }

  async searchLucidLink(filePrefix) {
    const result = { acceptFile: null, emisyjnyFile: null };

    try {
      // Look for LucidLink URLs
      const links = document.querySelectorAll('a[href^="lucid://"]');
      
      for (const link of links) {
        const lucidUrl = link.href;
        console.log('🔗 Found LucidLink URL:', lucidUrl);
        
        // Parse LucidLink URL to local path
        const localPath = this.parseLucidLinkToLocalPath(lucidUrl);
        console.log('📂 LucidLink local path:', localPath);
        
        // This would also require native file access
        // For now, just log for manual verification
        break;
      }
    } catch (error) {
      console.log('LucidLink search failed:', error);
    }

    return result;
  }

  async findSectionElement(sectionName) {
    // Use various selectors to find section elements
    const selectors = [
      `//*[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '${sectionName.toLowerCase()}')]`,
      `//td[contains(text(), '${sectionName}')]`,
      `//th[contains(text(), '${sectionName}')]`,
      `//div[contains(text(), '${sectionName}')]`,
      `//span[contains(text(), '${sectionName}')]`
    ];

    for (const selector of selectors) {
      try {
        const result = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        if (result.singleNodeValue) {
          return result.singleNodeValue;
        }
      } catch (error) {
        continue;
      }
    }

    return null;
  }

  async findFilesInElement(element) {
    const files = [];
    
    // Look for file links in the element and its siblings
    const links = element.querySelectorAll('a[href]');
    const siblingLinks = element.parentElement ? 
      element.parentElement.querySelectorAll('a[href]') : [];
    
    const allLinks = [...links, ...siblingLinks];
    
    for (const link of allLinks) {
      const href = link.href;
      const filename = this.extractFilenameFromUrl(href);
      
      if (this.isVideoFile(filename) || this.isArchiveFile(filename)) {
        files.push({
          name: filename,
          url: href,
          element: link,
          type: this.getFileType(href)
        });
      }
    }

    return files;
  }

  async downloadFile(fileInfo, customFilename = null) {
    try {
      const filename = customFilename || fileInfo.name;
      console.log(`⬇️ Downloading file: ${filename}`);

      if (fileInfo.type === 'cradle_attachment') {
        return await this.downloadCradleFile(fileInfo.url, filename);
      } else if (fileInfo.type === 'external_link') {
        return await this.downloadExternalFile(fileInfo.url, filename);
      } else {
        // Try direct download
        return await this.downloadCradleFile(fileInfo.url, filename);
      }
    } catch (error) {
      console.error(`Failed to download file ${fileInfo.name}:`, error);
      throw error;
    }
  }

  async downloadCradleFile(url, filename) {
    try {
      // Use Chrome downloads API through background script
      await chrome.runtime.sendMessage({
        action: 'DOWNLOAD_FILE',
        url: url,
        filename: `${this.downloadDir}/${filename}`
      });

      return {
        name: filename,
        path: `${this.downloadDir}/${filename}`,
        url: url,
        downloadedAt: new Date().toISOString()
      };
    } catch (error) {
      throw new Error(`Failed to download Cradle file: ${error.message}`);
    }
  }

  async downloadExternalFile(url, filename) {
    // For external files, we might need to handle CORS
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      
      await chrome.runtime.sendMessage({
        action: 'DOWNLOAD_FILE',
        url: downloadUrl,
        filename: `${this.downloadDir}/${filename}`
      });

      return {
        name: filename,
        path: `${this.downloadDir}/${filename}`,
        url: url,
        downloadedAt: new Date().toISOString()
      };
    } catch (error) {
      throw new Error(`Failed to download external file: ${error.message}`);
    }
  }

  // Utility methods
  matchesSection(text, section) {
    const normalizedText = text.toLowerCase().replace(/[^a-z0-9]/g, '');
    const normalizedSection = section.toLowerCase().replace(/[^a-z0-9]/g, '');
    return normalizedText.includes(normalizedSection) || normalizedSection.includes(normalizedText);
  }

  isVideoFile(filename) {
    if (!filename) return false;
    return this.videoExtensions.some(ext => filename.toLowerCase().endsWith(ext));
  }

  isArchiveFile(filename) {
    if (!filename) return false;
    return this.archiveExtensions.some(ext => filename.toLowerCase().endsWith(ext));
  }

  getFileType(url) {
    if (url.startsWith('http')) {
      return url.includes(window.location.hostname) ? 'cradle_attachment' : 'external_link';
    } else if (url.startsWith('lucid://')) {
      return 'lucidlink';
    } else if (url.startsWith('/Volumes/')) {
      return 'network_path';
    } else {
      return 'relative_link';
    }
  }

  extractFilenameFromUrl(url) {
    try {
      const urlObj = new URL(url, window.location.origin);
      const pathname = urlObj.pathname;
      return pathname.split('/').pop() || 'unknown_file';
    } catch (error) {
      // Fallback for relative URLs or malformed URLs
      return url.split('/').pop().split('?')[0] || 'unknown_file';
    }
  }

  extractFilePrefix(filename) {
    // Extract first 13 characters as prefix (based on original code)
    return filename.substring(0, 13);
  }

  parseLucidLinkToLocalPath(lucidUrl) {
    try {
      const url = new URL(lucidUrl);
      const hostname = url.hostname;
      const pathname = decodeURIComponent(url.pathname);
      return `/Volumes/${hostname}${pathname}`;
    } catch (error) {
      console.error('Failed to parse LucidLink URL:', error);
      return null;
    }
  }
}

// Initialize file downloader
if (!window.fileDownloader) {
  window.fileDownloader = new FileDownloader();
}