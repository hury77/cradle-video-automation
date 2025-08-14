// cradle-scanner.js - Main automation orchestrator
class CradleScanner {
  constructor() {
    this.isRunning = false;
    this.maxTasks = 5;
    this.currentTask = 0;
    this.processedAssets = [];
    
    this.fileDownloader = new FileDownloader();
    this.videoCompare = new VideoCompareAutomator();
    this.notifier = new NotificationManager();
    
    this.init();
  }

  init() {
    // Listen for messages from popup
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message, sender, sendResponse);
      return true; // Keep channel open
    });

    console.log('🎬 Cradle Scanner initialized');
  }

  async handleMessage(message, sender, sendResponse) {
    try {
      switch (message.action) {
        case 'PING':
          sendResponse({ pong: true });
          break;

        case 'START_AUTOMATION':
          await this.startAutomation(message.maxTasks);
          sendResponse({ success: true });
          break;

        case 'STOP_AUTOMATION':
          this.stopAutomation();
          sendResponse({ success: true });
          break;

        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    } catch (error) {
      console.error('Scanner error:', error);
      sendResponse({ success: false, error: error.message });
    }
  }

  async startAutomation(maxTasks = 5) {
    if (this.isRunning) {
      throw new Error('Automation is already running');
    }

    this.isRunning = true;
    this.maxTasks = maxTasks;
    this.currentTask = 0;
    this.processedAssets = [];

    try {
      this.notifier.sendStatus('🔍 Navigating to My Team Tasks...', 'processing');
      
      // Step 1: Navigate to My Team Tasks
      await this.navigateToMyTeamTasks();
      
      // Step 2: Apply QA final proofreading filter
      await this.applyQAFilter();
      
      // Step 3: Scan for pending tasks
      const pendingTasks = await this.scanPendingTasks();
      
      if (pendingTasks.length === 0) {
        throw new Error('No pending QA final proofreading tasks found');
      }

      this.notifier.sendStatus(`Found ${pendingTasks.length} pending tasks`, 'info');
      this.notifier.logActivity(`📋 Found ${pendingTasks.length} pending tasks`, 'info');

      // Step 4: Process tasks
      const tasksToProcess = pendingTasks.slice(0, this.maxTasks);
      
      for (let i = 0; i < tasksToProcess.length && this.isRunning; i++) {
        const task = tasksToProcess[i];
        this.currentTask = i + 1;
        
        this.notifier.sendProgress(this.currentTask, tasksToProcess.length, `Processing ${task.prodName}`);
        this.notifier.logActivity(`🔄 Processing: ${task.prodName}`, 'info');

        try {
          await this.processAsset(task);
          this.processedAssets.push({
            ...task,
            status: 'completed',
            processedAt: new Date().toISOString()
          });
        } catch (error) {
          console.error(`Error processing asset ${task.prodName}:`, error);
          this.notifier.logActivity(`❌ Error processing ${task.prodName}: ${error.message}`, 'error');
          
          this.processedAssets.push({
            ...task,
            status: 'error',
            error: error.message,
            processedAt: new Date().toISOString()
          });
        }
      }

      // Complete
      const successCount = this.processedAssets.filter(a => a.status === 'completed').length;
      const errorCount = this.processedAssets.filter(a => a.status === 'error').length;

      this.notifier.sendAutomationComplete({
        processed: this.processedAssets.length,
        comparisons: successCount,
        errors: errorCount
      });

    } catch (error) {
      console.error('Automation error:', error);
      this.notifier.sendAutomationError(error.message);
    } finally {
      this.isRunning = false;
    }
  }

  stopAutomation() {
    this.isRunning = false;
    this.notifier.logActivity('⏹️ Automation stopped by user', 'warning');
  }

  async navigateToMyTeamTasks() {
    // Look for "My Team Tasks" tab/link
    const selectors = [
      "//span[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'my team tasks')]",
      "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'my team tasks')]",
      "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'my team tasks')]"
    ];

    for (const selector of selectors) {
      try {
        const element = await this.waitForElement(selector, 10000);
        if (element) {
          await this.clickElement(element);
          await this.waitForPageLoad();
          return true;
        }
      } catch (error) {
        continue;
      }
    }

    throw new Error('Could not find My Team Tasks navigation');
  }

  async applyQAFilter() {
    this.notifier.sendStatus('🔧 Applying QA final proofreading filter...', 'processing');

    // Look for the filter dropdown or direct filter option
    const filterSelectors = [
      "//select[contains(@name, 'filter') or contains(@name, 'state')]//option[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'qa final proofreading')]",
      "//*[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'qa final proofreading') and (self::button or self::a or self::span[@class='filter'] or contains(@class, 'filter'))]"
    ];

    for (const selector of filterSelectors) {
      try {
        const element = await this.waitForElement(selector, 5000);
        if (element) {
          await this.clickElement(element);
          await this.waitForPageLoad();
          await this.waitForSpinnerToDisappear();
          return true;
        }
      } catch (error) {
        continue;
      }
    }

    throw new Error('Could not find or apply QA final proofreading filter');
  }

  async scanPendingTasks() {
    this.notifier.sendStatus('🔍 Scanning for pending tasks...', 'processing');

    // Wait for table to load
    await this.waitForElement("//table//tbody//tr[1]", 15000);
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Find table headers to get column indices
    const headers = document.querySelectorAll('table th, table thead td');
    let prodNameIndex = -1;
    let statusIndex = -1;
    let deadlineIndex = -1;

    headers.forEach((header, index) => {
      const text = header.textContent.toLowerCase();
      if (text.includes('prod.name') || text.includes('product name')) {
        prodNameIndex = index;
      }
      if (text.includes('state') || text.includes('status')) {
        statusIndex = index;
      }
      if (text.includes('deadline') || text.includes('due')) {
        deadlineIndex = index;
      }
    });

    if (prodNameIndex === -1 || statusIndex === -1) {
      throw new Error('Could not find required table columns (Prod.Name, Status)');
    }

    // Sort by deadline if column exists
    if (deadlineIndex !== -1) {
      try {
        const deadlineHeader = headers[deadlineIndex];
        await this.clickElement(deadlineHeader);
        await this.waitForPageLoad();
        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (error) {
        console.log('Could not sort by deadline, continuing...');
      }
    }

    // Scan table rows for pending tasks
    const rows = document.querySelectorAll('table tbody tr');
    const pendingTasks = [];

    for (const row of rows) {
      const cells = row.querySelectorAll('td');
      
      if (cells.length > Math.max(prodNameIndex, statusIndex)) {
        const statusCell = cells[statusIndex];
        const prodNameCell = cells[prodNameIndex];
        
        const statusText = statusCell.textContent.toLowerCase().trim();
        
        if (statusText.includes('pending')) {
          const link = prodNameCell.querySelector('a');
          if (link) {
            const task = {
              prodName: prodNameCell.textContent.trim(),
              status: statusText,
              url: link.href,
              deadline: deadlineIndex !== -1 ? cells[deadlineIndex].textContent.trim() : null
            };
            pendingTasks.push(task);
          }
        }
      }
    }

    return pendingTasks;
  }

  async processAsset(task) {
    this.notifier.logActivity(`📂 Opening asset: ${task.prodName}`, 'info');

    // Open asset in new tab to avoid losing current page
    const newTab = window.open(task.url, '_blank');
    
    // Wait for new tab to load
    await new Promise(resolve => setTimeout(resolve, 3000));

    // Switch to new tab (this is tricky in content script, we'll work with current tab)
    // For now, navigate current tab
    window.location.href = task.url;
    await this.waitForPageLoad();

    try {
      // Take the task (click Pending -> Take)
      await this.takeTask();

      // Download files
      const files = await this.fileDownloader.getAssetFiles();
      
      if (!files.acceptFile || !files.emisyjnyFile) {
        throw new Error('Could not find required files (accept file and emisyjny file)');
      }

      // Start video comparison
      await this.videoCompare.startComparison(files.acceptFile, files.emisyjnyFile);
      
      this.notifier.logActivity(`✅ ${task.prodName}: Video comparison ready!`, 'success');

    } catch (error) {
      throw new Error(`Failed to process asset: ${error.message}`);
    }
  }

  async takeTask() {
    try {
      // Look for "Pending" button
      const pendingBtn = await this.waitForElement("//button[contains(translate(.,'PENDING','pending'),'pending')]", 10000);
      if (pendingBtn) {
        await this.clickElement(pendingBtn);
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Look for "Take" button in popup/modal
        const takeBtn = await this.waitForElement("//button[contains(translate(.,'TAKE','take'),'take')]", 5000);
        if (takeBtn) {
          await this.clickElement(takeBtn);
          await this.waitForPageLoad();
        }
      }
    } catch (error) {
      console.log('Could not take task, might already be assigned:', error.message);
    }
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

  async waitForSpinnerToDisappear() {
    try {
      // Wait for any loading spinners to disappear
      const spinnerSelectors = ['.spinner', '.loading', '[class*="loading"]', '[class*="spinner"]'];
      
      for (const selector of spinnerSelectors) {
        const spinners = document.querySelectorAll(selector);
        if (spinners.length > 0) {
          await this.waitForElementsToDisappear(spinners, 30000);
        }
      }
    } catch (error) {
      console.log('No spinner found or timeout, continuing...');
    }
  }

  async waitForElementsToDisappear(elements, timeout = 30000) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      
      const check = () => {
        const visible = Array.from(elements).some(el => 
          el.offsetParent !== null && 
          window.getComputedStyle(el).display !== 'none'
        );
        
        if (!visible) {
          resolve();
        } else if (Date.now() - startTime > timeout) {
          resolve(); // Timeout, but don't fail
        } else {
          setTimeout(check, 500);
        }
      };
      
      check();
    });
  }
}

// Initialize scanner when content script loads
if (!window.cradleScanner) {
  window.cradleScanner = new CradleScanner();
}