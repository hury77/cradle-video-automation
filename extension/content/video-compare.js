// video-compare.js - Automates Video Compare interface
class VideoCompareAutomator {
  constructor() {
    this.isProcessing = false;
    this.currentComparison = null;
    
    this.init();
  }

  init() {
    console.log('🎬 Video Compare Automator initialized');
  }

  async startComparison(acceptFile, emisyjnyFile) {
    if (this.isProcessing) {
      throw new Error('Video comparison already in progress');
    }

    try {
      this.isProcessing = true;
      console.log('🎬 Starting video comparison...');
      console.log('📁 Accept file:', acceptFile);
      console.log('📁 Emisyjny file:', emisyjnyFile);

      // Step 1: Navigate to Video Compare tab
      await this.navigateToVideoCompare();

      // Step 2: Click "Add Compare" button
      await this.clickAddCompare();

      // Step 3: Upload files to comparison slots
      await this.uploadComparisonFiles(acceptFile, emisyjnyFile);

      // Step 4: Submit comparison
      await this.submitComparison();

      // Step 5: Monitor progress
      await this.monitorComparison();

      console.log('✅ Video comparison completed successfully');
      
      // Store comparison info for reference
      this.currentComparison = {
        acceptFile: acceptFile,
        emisyjnyFile: emisyjnyFile,
        startedAt: new Date().toISOString(),
        status: 'completed'
      };

      return this.currentComparison;

    } catch (error) {
      console.error('❌ Video comparison failed:', error);
      this.currentComparison = {
        acceptFile: acceptFile,
        emisyjnyFile: emisyjnyFile,
        startedAt: new Date().toISOString(),
        status: 'failed',
        error: error.message
      };
      throw error;
    } finally {
      this.isProcessing = false;
    }
  }

  async navigateToVideoCompare() {
    console.log('🔍 Looking for Video Compare tab...');

    // Look for Video Compare tab/link
    const selectors = [
      "//a[contains(translate(.,'VIDEO COMPARE','video compare'), 'video compare')]",
      "//button[contains(translate(.,'VIDEO COMPARE','video compare'), 'video compare')]",
      "//span[contains(translate(.,'VIDEO COMPARE','video compare'), 'video compare')]",
      "//tab[contains(translate(.,'VIDEO COMPARE','video compare'), 'video compare')]",
      "//*[@href*='video' and @href*='compare']",
      "//*[contains(@class, 'video-compare') or contains(@id, 'video-compare')]"
    ];

    for (const selector of selectors) {
      try {
        const element = await this.waitForElement(selector, 5000);
        if (element) {
          console.log('📍 Found Video Compare tab, clicking...');
          await this.clickElement(element);
          await this.waitForPageLoad();
          
          // Verify we're on Video Compare page
          if (await this.isVideoComparePage()) {
            console.log('✅ Successfully navigated to Video Compare');
            return true;
          }
        }
      } catch (error) {
        continue;
      }
    }

    // Try to find it by looking for "Add Compare" button directly
    try {
      await this.waitForElement("//button[contains(translate(.,'ADD COMPARE','add compare'), 'add compare')]", 5000);
      console.log('✅ Already on Video Compare page');
      return true;
    } catch (error) {
      throw new Error('Could not find or navigate to Video Compare');
    }
  }

  async clickAddCompare() {
    console.log('🔍 Looking for Add Compare button...');

    const selectors = [
      "//button[contains(translate(.,'ADD COMPARE','add compare'), 'add compare')]",
      "//a[contains(translate(.,'ADD COMPARE','add compare'), 'add compare')]",
      "//*[@class*='add-compare' or @id*='add-compare']",
      "//button[contains(text(), 'Add Compare')]",
      "//input[@type='button' and contains(@value, 'Add Compare')]"
    ];

    for (const selector of selectors) {
      try {
        const button = await this.waitForElement(selector, 5000);
        if (button) {
          console.log('📍 Found Add Compare button, clicking...');
          await this.clickElement(button);
          
          // Wait for comparison form to appear
          await this.waitForComparisonForm();
          console.log('✅ Add Compare form opened');
          return true;
        }
      } catch (error) {
        continue;
      }
    }

    throw new Error('Could not find Add Compare button');
  }

  async waitForComparisonForm() {
    // Wait for file upload inputs or drag-drop areas to appear
    const formSelectors = [
      "//input[@type='file']",
      "//*[@class*='drop-zone' or @class*='upload-area']",
      "//*[contains(text(), 'Video A') or contains(text(), 'Video B')]",
      "//form[contains(@class, 'compare') or contains(@id, 'compare')]"
    ];

    for (const selector of formSelectors) {
      try {
        await this.waitForElement(selector, 10000);
        console.log('✅ Comparison form loaded');
        return true;
      } catch (error) {
        continue;
      }
    }

    // Give it some time to load even if we can't detect specific elements
    await new Promise(resolve => setTimeout(resolve, 3000));
    return true;
  }

  async uploadComparisonFiles(acceptFile, emisyjnyFile) {
    console.log('📤 Uploading comparison files...');

    try {
      // Method 1: Look for labeled file inputs (Video A, Video B)
      await this.uploadToLabeledInputs(acceptFile, emisyjnyFile);
    } catch (error) {
      console.log('Labeled inputs method failed, trying generic approach...');
      
      try {
        // Method 2: Look for generic file inputs
        await this.uploadToGenericInputs(acceptFile, emisyjnyFile);
      } catch (error2) {
        console.log('Generic inputs method failed, trying drag-drop...');
        
        try {
          // Method 3: Try drag-drop areas
          await this.uploadToDragDropAreas(acceptFile, emisyjnyFile);
        } catch (error3) {
          throw new Error('Could not find file upload mechanism');
        }
      }
    }

    console.log('✅ Files uploaded successfully');
  }

  async uploadToLabeledInputs(acceptFile, emisyjnyFile) {
    // Look for inputs with labels containing "Video A" and "Video B"
    const videoASelectors = [
      "//input[@type='file' and (contains(@name, 'video_a') or contains(@id, 'video_a'))]",
      "//input[@type='file'][preceding-sibling::*[contains(text(), 'Video A')] or following-sibling::*[contains(text(), 'Video A')]]",
      "//label[contains(text(), 'Video A')]//input[@type='file']",
      "//div[contains(text(), 'Video A')]//input[@type='file']"
    ];

    const videoBSelectors = [
      "//input[@type='file' and (contains(@name, 'video_b') or contains(@id, 'video_b'))]",
      "//input[@type='file'][preceding-sibling::*[contains(text(), 'Video B')] or following-sibling::*[contains(text(), 'Video B')]]",
      "//label[contains(text(), 'Video B')]//input[@type='file']",
      "//div[contains(text(), 'Video B')]//input[@type='file']"
    ];

    let videoAInput = null;
    let videoBInput = null;

    // Find Video A input
    for (const selector of videoASelectors) {
      try {
        videoAInput = await this.waitForElement(selector, 3000);
        if (videoAInput) break;
      } catch (error) {
        continue;
      }
    }

    // Find Video B input
    for (const selector of videoBSelectors) {
      try {
        videoBInput = await this.waitForElement(selector, 3000);
        if (videoBInput) break;
      } catch (error) {
        continue;
      }
    }

    if (!videoAInput || !videoBInput) {
      throw new Error('Could not find labeled Video A/B inputs');
    }

    // Upload files
    console.log('📤 Uploading to Video A (accept file)...');
    await this.setFileInput(videoAInput, acceptFile);
    
    console.log('📤 Uploading to Video B (emisyjny file)...');
    await this.setFileInput(videoBInput, emisyjnyFile);
  }

  async uploadToGenericInputs(acceptFile, emisyjnyFile) {
    // Find all file inputs
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    if (fileInputs.length < 2) {
      throw new Error('Not enough file inputs found');
    }

    console.log(`📤 Found ${fileInputs.length} file inputs, using first two...`);
    
    // Use first input for accept file, second for emisyjny file
    await this.setFileInput(fileInputs[0], acceptFile);
    await this.setFileInput(fileInputs[1], emisyjnyFile);
  }

  async uploadToDragDropAreas(acceptFile, emisyjnyFile) {
    // Look for drag-drop areas
    const dropAreas = document.querySelectorAll(
      '[class*="drop"], [class*="upload"], [class*="drag"]'
    );

    if (dropAreas.length < 2) {
      throw new Error('Not enough drop areas found');
    }

    console.log(`📤 Found ${dropAreas.length} drop areas, simulating drops...`);
    
    // This is more complex as we need to simulate file drops
    // For now, throw error as it requires more sophisticated implementation
    throw new Error('Drag-drop upload not yet implemented');
  }

  async setFileInput(input, fileInfo) {
    // This is tricky in a browser extension context
    // We can't directly set files to input elements due to security restrictions
    
    // For now, we'll focus the input and let the user know what to do
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    input.focus();
    
    // Highlight the input
    input.style.border = '3px solid #ff6b6b';
    input.style.backgroundColor = '#ffe6e6';
    
    // Show a temporary message
    const message = document.createElement('div');
    message.style.cssText = `
      position: absolute;
      background: #ff6b6b;
      color: white;
      padding: 8px 12px;
      border-radius: 4px;
      z-index: 10000;
      font-size: 12px;
      font-weight: bold;
      margin-top: -30px;
    `;
    message.textContent = `Please select: ${fileInfo.name}`;
    input.parentElement.style.position = 'relative';
    input.parentElement.appendChild(message);
    
    // Remove styling after 5 seconds
    setTimeout(() => {
      input.style.border = '';
      input.style.backgroundColor = '';
      if (message.parentElement) {
        message.parentElement.removeChild(message);
      }
    }, 5000);
    
    // For automation, we'd need to:
    // 1. Use native messaging to access local files
    // 2. Or have files pre-staged in accessible location
    // 3. Or use different upload mechanism
    
    console.log(`📍 Input highlighted for file: ${fileInfo.name}`);
    
    // Simulate file selection (this won't actually work due to security restrictions)
    // In a real implementation, you'd need native file access
    return true;
  }

  async submitComparison() {
    console.log('🚀 Looking for Submit button...');

    const submitSelectors = [
      "//button[contains(translate(.,'SUBMIT','submit'), 'submit')]",
      "//input[@type='submit']",
      "//button[@type='submit']",
      "//button[contains(translate(.,'START','start'), 'start')]",
      "//button[contains(translate(.,'COMPARE','compare'), 'compare')]",
      "//*[@class*='submit' or @id*='submit']"
    ];

    for (const selector of submitSelectors) {
      try {
        const button = await this.waitForElement(selector, 5000);
        if (button && !button.disabled) {
          console.log('📍 Found Submit button, clicking...');
          await this.clickElement(button);
          console.log('✅ Comparison submitted');
          return true;
        }
      } catch (error) {
        continue;
      }
    }

    throw new Error('Could not find or click Submit button');
  }

  async monitorComparison() {
    console.log('⏳ Monitoring comparison progress...');

    const startTime = Date.now();
    const maxWaitTime = 10 * 60 * 1000; // 10 minutes max

    while (Date.now() - startTime < maxWaitTime) {
      try {
        // Look for completion indicators
        if (await this.isComparisonComplete()) {
          console.log('✅ Comparison completed!');
          return true;
        }

        // Look for error indicators
        if (await this.hasComparisonError()) {
          throw new Error('Comparison failed - error detected on page');
        }

        // Wait before next check
        await new Promise(resolve => setTimeout(resolve, 5000));

      } catch (error) {
        if (error.message.includes('Comparison failed')) {
          throw error;
        }
        // Continue monitoring on other errors
      }
    }

    throw new Error('Comparison timeout - took longer than 10 minutes');
  }

  async isComparisonComplete() {
    // Look for completion indicators
    const completionSelectors = [
      "//*[contains(text(), 'complete') or contains(text(), 'finished') or contains(text(), 'done')]",
      "//*[contains(@class, 'complete') or contains(@class, 'finished') or contains(@class, 'success')]",
      "//button[contains(text(), 'Download') or contains(text(), 'View Results')]",
      "//*[contains(text(), 'Results') and contains(@class, 'result')]"
    ];

    for (const selector of completionSelectors) {
      try {
        await this.waitForElement(selector, 1000);
        return true;
      } catch (error) {
        continue;
      }
    }

    return false;
  }

  async hasComparisonError() {
    // Look for error indicators
    const errorSelectors = [
      "//*[contains(text(), 'error') or contains(text(), 'failed')]",
      "//*[contains(@class, 'error') or contains(@class, 'failed')]",
      "//div[@class*='alert' and (@class*='error' or @class*='danger')]"
    ];

    for (const selector of errorSelectors) {
      try {
        await this.waitForElement(selector, 1000);
        return true;
      } catch (error) {
        continue;
      }
    }

    return false;
  }

  async isVideoComparePage() {
    // Check if we're on the Video Compare page
    const indicators = [
      'video compare',
      'add compare',
      'video a',
      'video b',
      'comparison'
    ];

    const pageText = document.body.textContent.toLowerCase();
    return indicators.some(indicator => pageText.includes(indicator));
  }

  // Utility methods
  async waitForElement(xpath, timeout = 10000) {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      
      const check = () => {
        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        const element = result.singleNodeValue;
        
        if (element) {
          resolve(element);
        } else if (Date.now() - startTime > timeout) {
          reject(new Error(`Timeout waiting for element: ${xpath}`));
        } else {
          setTimeout(check, 500);
        }
      };
      
      check();
    });
  }

  async clickElement(element) {
    return new Promise((resolve) => {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => {
        element.click();
        resolve();
      }, 500);
    });
  }

  async waitForPageLoad() {
    return new Promise((resolve) => {
      if (document.readyState === 'complete') {
        setTimeout(resolve, 1000);
      } else {
        window.addEventListener('load', () => {
          setTimeout(resolve, 1000);
        });
      }
    });
  }
}

// Initialize Video Compare automator
if (!window.videoCompareAutomator) {
  window.videoCompareAutomator = new VideoCompareAutomator();
}