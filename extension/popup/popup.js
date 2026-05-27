// Popup script for Manifest V3
class PopupController {
  constructor() {
    this.isRunning = false;
    this.init();
  }

  init() {
    console.log("Popup initializing...");

    // Get DOM elements
    this.startBtn = document.getElementById("startBtn");
    this.stopBtn = document.getElementById("stopBtn");
    this.findBtn = document.getElementById("findBtn");
    this.takeBtn = document.getElementById("takeBtn");
    this.downloadBtn = document.getElementById("downloadBtn");
    this.statusBtn = document.getElementById("statusBtn");
    this.statusDiv = document.getElementById("status");
    this.logDiv = document.getElementById("log");
    this.videoCompareBtn = document.getElementById("videoCompareBtn");
    this.useApiCheckbox = document.getElementById("useApiCheckbox");
    this.clientFilterInput = document.getElementById("clientFilterInput");
    this.clearFilterBtn    = document.getElementById("clearFilterBtn");
    this.clientHistoryList = document.getElementById("clientHistory");

    // Load saved state
    const useApiState = localStorage.getItem("cradle_use_api") === "true";
    if (this.useApiCheckbox) {
      this.useApiCheckbox.checked = useApiState;
      this.useApiCheckbox.addEventListener("change", (e) => {
        localStorage.setItem("cradle_use_api", e.target.checked);
      });
    }

    // --- Filtr klienta ---
    if (this.clientFilterInput) {
      chrome.storage.local.get(["cradle_client_filter", "cradle_client_history"], (result) => {
        this.clientFilterInput.value = result.cradle_client_filter || "";
        const history = result.cradle_client_history || [];
        history.forEach(name => {
          const opt = document.createElement("option");
          opt.value = name;
          this.clientHistoryList.appendChild(opt);
        });
      });
      this.clientFilterInput.addEventListener("input", (e) => {
        const val = e.target.value.trim();
        if (val) {
          chrome.storage.local.set({ cradle_client_filter: val });
        } else {
          chrome.storage.local.remove("cradle_client_filter");
        }
      });
    }
    if (this.clearFilterBtn) {
      this.clearFilterBtn.addEventListener("click", () => {
        this.clientFilterInput.value = "";
        chrome.storage.local.remove("cradle_client_filter");
        this.log("🏢 Filtr klienta wyczyszczony");
      });
    }
    // --- koniec filtru klienta ---

    // Bind event listeners
    this.startBtn.addEventListener("click", () => this.startAutomation());
    this.stopBtn.addEventListener("click", () => this.stopAutomation());
    this.findBtn.addEventListener("click", () => this.findAsset());
    this.takeBtn.addEventListener("click", () => this.takeAsset());
    this.downloadBtn.addEventListener("click", () => this.downloadFiles());
    this.statusBtn.addEventListener("click", () => this.checkStatus());
    this.videoCompareBtn.addEventListener("click", () =>
      this.startVideoCompare()
    );

    // Check initial status
    this.checkStatus();

    console.log("Popup initialized");
  }

  async sendCommandToContentScript(action, data = {}) {
    try {
      // Get active tab
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });

      if (!tab || !tab.url.includes("cradle.egplusww.pl")) {
        throw new Error("Please navigate to Cradle first");
      }

      // Use Manifest V3 API
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (action, data) => {
          document.dispatchEvent(
            new CustomEvent("extension-command", {
              detail: { action: action, data: data },
            })
          );
        },
        args: [action, data],
      });

      this.log(`✅ Command sent: ${action}`);
      return { success: true };
    } catch (error) {
      console.error("Failed to send command:", error);
      this.log(`❌ Error: ${error.message}`, "error");
      throw error;
    }
  }

  async startAutomation() {
    try {
      chrome.storage.local.get("cradle_client_filter", async (result) => {
        const activeFilter = result.cradle_client_filter || "";
        if (activeFilter) {
          this.log(`🚀 Starting automation (filtr: "${activeFilter}")...`);
        } else {
          this.log("🚀 Starting automation...");
        }
        this.updateUI(true);
        try {
          await this.sendCommandToContentScript("START_AUTOMATION");
          this.monitorAutomation();
        } catch (error) {
          this.log(`❌ Failed to start: ${error.message}`, "error");
          this.updateUI(false);
        }
      });
    } catch (error) {
      this.log(`❌ Failed to start: ${error.message}`, "error");
      this.updateUI(false);
    }
  }

  async stopAutomation() {
    try {
      this.log("⏹️ Stopping automation...");

      await this.sendCommandToContentScript("STOP_AUTOMATION");
      this.updateUI(false);
    } catch (error) {
      this.log(`❌ Failed to stop: ${error.message}`, "error");
    }
  }

  async findAsset() {
    try {
      this.log("🔍 Finding pending asset...");
      await this.sendCommandToContentScript("FIND_ASSET");
    } catch (error) {
      this.log(`❌ Find asset failed: ${error.message}`, "error");
    }
  }

  async takeAsset() {
    try {
      this.log("✋ Taking asset...");
      await this.sendCommandToContentScript("TAKE_ASSET");
    } catch (error) {
      this.log(`❌ Take asset failed: ${error.message}`, "error");
    }
  }

  async downloadFiles() {
    try {
      this.log("📁 Starting file download...");
      await this.sendCommandToContentScript("DOWNLOAD_FILES");
    } catch (error) {
      this.log(`❌ Download failed: ${error.message}`, "error");
    }
  }

  async checkStatus() {
    try {
      await this.sendCommandToContentScript("GET_STATUS");
    } catch (error) {
      this.log(`❌ Status check failed: ${error.message}`, "error");
    }
  }

  monitorAutomation() {
    // This could be enhanced to listen for status updates
    setTimeout(() => {
      if (this.isRunning) {
        this.checkStatus();
        this.monitorAutomation();
      }
    }, 2000);
  }

  updateUI(running) {
    this.isRunning = running;

    if (running) {
      this.statusDiv.textContent = "🔄 Running...";
      this.statusDiv.className = "status running";
    } else {
      this.statusDiv.textContent = "⏹️ Stopped";
      this.statusDiv.className = "status stopped";
    }
  }

  log(message, type = "info") {
    console.log(message);

    if (this.logDiv) {
      const logEntry = document.createElement("div");
      logEntry.className = `log-entry ${type}`;
      logEntry.textContent = `${new Date().toLocaleTimeString()}: ${message}`;

      this.logDiv.appendChild(logEntry);
      this.logDiv.scrollTop = this.logDiv.scrollHeight;

      // Keep only last 10 entries
      while (this.logDiv.children.length > 10) {
        this.logDiv.removeChild(this.logDiv.firstChild);
      }
    }
  }
  async startVideoCompare() {
    const useApi = this.useApiCheckbox ? this.useApiCheckbox.checked : false;
    this.log(`🎬 Starting Video Compare (API: ${useApi})...`);
    try {
      await this.sendCommandToContentScript("VIDEO_COMPARE", { useApi });
      this.log("✅ Video Compare request sent");
    } catch (error) {
      this.log(`❌ Video Compare error: ${error.message}`, "error");
    }
  }
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  new PopupController();
});
