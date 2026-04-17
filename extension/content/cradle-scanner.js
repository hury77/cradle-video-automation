console.log("Cradle Scanner content script loaded");

// WebSocket connection to Desktop App
class DesktopConnection {
  constructor() {
    this.ws = null;
    this.reconnectDelay = 2000;
    this.maxReconnectAttempts = 5;
    this.reconnectAttempts = 0;
    this.connect();
  }

  connect() {
    try {
      this.ws = new WebSocket("ws://localhost:8765");

      this.ws.onopen = () => {
        console.log("🔗 Connected to Desktop App");
        this.reconnectAttempts = 0;
        this.sendMessage({
          action: "extension_connected",
          timestamp: Date.now(),
        });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("📨 Message from Desktop App:", data);

          const scanner = window.cradleScanner;
          if (!scanner) return;

          // Handle specific response types
          if (data.action === "DOWNLOAD_COMPLETED" || data.action === "DOWNLOAD_RESULTS") {
            const d = data.data || {};
            if (d.errors && d.errors.length > 0) {
              for (const err of d.errors) {
                const msg = err.error || "Unknown download error";
                scanner.showNotification(`❌ Desktop App: ${msg}`, "error");
              }
            }
            if (d.files_downloaded && d.files_downloaded.length > 0) {
              for (const f of d.files_downloaded) {
                scanner.showNotification(`✅ Desktop App: ${f.filename || "file"} downloaded`, "success");
              }
            }
            
            // Trigger auto-compare ONLY when download is fully completed, not for intermediate results
            if (data.action === "DOWNLOAD_COMPLETED") {
                if (scanner.isAutoComparing || localStorage.getItem("cradle-auto-video-compare") === "true") {
                  console.log("[CradleScanner] 🔄 Auto-compare: Downloads complete. Triggering Video Compare...");
                  scanner.isAutoComparing = true; // ensure in-memory flag is also set
                  setTimeout(() => {
                    scanner.startVideoCompare({ useApi: true });
                  }, 2000);
                }
            }
          } else if (data.action === "VIDEO_COMPARE_RESULTS") {
            const resultData = data.data || {};
            console.log("[CradleScanner] 📊 Video Compare Results Received:", resultData);
            
            if (resultData.success !== false && !resultData.error) {
               scanner.showNotification(`✅ Video Compare: Success! (Job ${resultData.job_id || 'new'})`, "success");
               
               // LOG: check if we are in automation mode
               console.log("[CradleScanner] 🤖 Automation Mode Check - isAutoComparing:", scanner.isAutoComparing);
               
               if (scanner.isAutoComparing) {
                  scanner.isAutoComparing = false;
                  localStorage.removeItem("cradle-auto-video-compare"); // Clear persistence
                  
                  scanner.showNotification("🤖 Processing complete. Triggering Agent Hand-off...", "info");
                  console.log("[CradleScanner] 🚀 Starting Hand-off process (Agent 2 -> Agent 1)");

                  // Use a slightly longer delay to ensure notifications are visible
                  setTimeout(() => {
                    // Open results in new tab first (if ID exists)
                    if (resultData.job_id) {
                        console.log(`[CradleScanner] 🌍 Opening results for Job ${resultData.job_id}`);
                        window.open(`http://localhost:3000/compare/${resultData.job_id}`, '_blank');
                    }

                    // Then prompt on this tab
                    const returnToTasks = window.confirm(
                      `🤖 Agent 2 (Analyst): Analysis complete!\n\n` +
                      `Return to "My Team Tasks" to scan for next assets?`
                    );

                    if (returnToTasks) {
                        console.log("[CradleScanner] 🚀 User approved hand-off. Navigating back to Tasks...");
                        localStorage.setItem("cradle-auto-apply-qa-filter", "true");
                        window.location.href = "https://cradle.egplusww.pl/my-team/";
                    } else {
                        console.log("[CradleScanner] ⏸️ User chose to stay on this page.");
                        scanner.showNotification("Automation paused.", "warning");
                    }
                  }, 1500);
               } else {
                  console.log("[CradleScanner] ℹ️ Not in auto-compare mode, skipping hand-off prompt.");
                  if (resultData.job_id) {
                      window.open(`http://localhost:3000/compare/${resultData.job_id}`, '_blank');
                  }
               }
            } else {
               const errorMsg = resultData.error || resultData.message || 'Unknown error';
               console.error("[CradleScanner] ❌ Video Compare Error:", errorMsg);
               scanner.showNotification(`❌ Video Compare error: ${errorMsg}`, "error");
               
               if (scanner.isAutoComparing) {
                  scanner.isAutoComparing = false;
                  localStorage.removeItem("cradle-auto-video-compare");
                  localStorage.setItem("cradle-automation-stopped", "true");
                  scanner.showNotification("🚫 Automation STOPPED due to error.", "error");
               }
            }
          } else if (data.action === "FILE_MOVED") {
            console.log(`[Desktop] 📦 File moved: ${data.data?.filename}`);
          } else if (data.action === "STATUS_UPDATE") {
            const statusMsg = data.details?.message || data.status || "Processing...";
            console.log(`[Desktop] ℹ️ Status: ${statusMsg}`);
            scanner.showNotification(`System status: ${statusMsg}`, "info");
          } else if (data.action === "UPLOAD_SLOW") {
            const cradleId = data.data?.cradle_id;
            console.warn(`[Desktop] 🐢 UPLOAD_SLOW: ${data.data?.status}`);
            
            // Show a custom popup forcing the user to make a choice
            const popup = document.createElement("div");
            popup.style.position = "fixed";
            popup.style.bottom = "20px";
            popup.style.right = "20px";
            popup.style.backgroundColor = "#ff9800";
            popup.style.color = "white";
            popup.style.padding = "20px";
            popup.style.borderRadius = "8px";
            popup.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
            popup.style.zIndex = "99999";
            popup.style.fontFamily = "system-ui, sans-serif";
            
            popup.innerHTML = `
                <h3 style="margin-top:0; margin-bottom: 10px;">⚠️ Heavy Upload Detected</h3>
                <p style="margin:0 0 15px 0;">Upload for Cradle ${cradleId || 'Asset'} is taking over 60 seconds.</p>
                <div style="display:flex; justify-content:flex-end; gap: 10px;">
                    <button id="cancel-upload-btn-x" style="padding: 8px 12px; border:none; border-radius:4px; background:#d32f2f; color:white; cursor:pointer; font-weight:bold;">Kill Process</button>
                    <button id="wait-upload-btn-x" style="padding: 8px 12px; border:none; border-radius:4px; background:#1976d2; color:white; cursor:pointer; font-weight:bold;">Keep Waiting</button>
                </div>
            `;
            
            document.body.appendChild(popup);
            
            document.getElementById("wait-upload-btn-x").addEventListener("click", () => {
                popup.remove();
                scanner.showNotification("Waiting for upload to finish...", "info");
            });
            
            document.getElementById("cancel-upload-btn-x").addEventListener("click", () => {
                popup.remove();
                scanner.showNotification("Cancelling upload...", "warning");
                // Stop any auto-compare state
                if (scanner.isAutoComparing) {
                    scanner.isAutoComparing = false;
                    localStorage.removeItem("cradle-auto-video-compare");
                    localStorage.setItem("cradle-automation-stopped", "true");
                }
                // Send kill message to server
                this.sendMessage({
                    action: "VIDEO_COMPARE_CANCEL",
                    cradleId: cradleId
                });
            });
          } else if (data.action === "ERROR") {
            const msg = data.data?.error || data.error || "Unknown error";
            console.error("[Desktop] ❌ ERROR:", msg);
            scanner.showNotification(`❌ Desktop App error: ${msg}`, "error");
            
            // Un-hang the UI if we were auto-comparing
            if (scanner.isAutoComparing) {
                scanner.isAutoComparing = false;
                localStorage.removeItem("cradle-auto-video-compare");
                localStorage.setItem("cradle-automation-stopped", "true");
                scanner.showNotification("🚫 Automation STOPPED due to error.", "error");
            }
            // Remove processing UI classes if present
            document.body.classList.remove("cradle-processing");
          }
        } catch (e) {
          console.error("Failed to parse message:", event.data);
        }
      };

      this.ws.onclose = () => {
        console.log("❌ Disconnected from Desktop App");
        this.reconnect();
      };

      this.ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };
    } catch (error) {
      console.error("Failed to connect to Desktop App:", error);
      this.reconnect();
    }
  }

  sendMessage(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    console.warn("Desktop App not connected");
    return false;
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(
        `🔄 Reconnecting to Desktop App (${this.reconnectAttempts}/${this.maxReconnectAttempts})`
      );
      setTimeout(() => this.connect(), this.reconnectDelay);
    }
  }
}

// Global desktop connection
const desktopConnection = new DesktopConnection();

class CradleScanner {
  constructor() {
    this.isScanning = false;
    this.isAutoComparing = false;
    this.status = "Ready";
    this.currentCradleId = null;

    document.addEventListener("extension-command", async (event) => {
      await this.handleCommand(event);
    });

    this.checkAutoApplyFilter();
    this.checkAutoFindAsset();
    this.checkAutoTakeAsset();
    this.extractCradleId();

    // Storage listener do komunikacji między kartami (Base Tab <-> Worker Tab)
    window.addEventListener('storage', async (e) => {
      if (e.key === 'cradle-trigger-next' && e.newValue) {
         console.log("[CradleScanner] 🔄 Otrzymano sygnał od zamkniętej karty worker'a by przetwarzać dalej!");
         
         if (localStorage.getItem("cradle-automation-stopped") === "true") {
             console.log("[CradleScanner] 🚫 Ignoruję sygnał. Automatyzacja została zatrzymana.");
             return;
         }
         
         if (window.location.href.includes("my-team")) {
             await this.wait(2000);
             this.findPendingAsset();
         }
      }
    });

    // Restore automation state from localStorage (survives page reloads)
    if (localStorage.getItem("cradle-auto-video-compare") === "true") {
      this.isAutoComparing = true;
      console.log("[CradleScanner] 🔄 Restored isAutoComparing=true from localStorage.");
    }

    console.log("[CradleScanner] Scanner initialized");
  }

  extractCradleId() {
    const urlMatch = window.location.href.match(
      /\/assets\/deliverable-details\/(\d+)/
    );
    if (urlMatch) {
      this.currentCradleId = urlMatch[1];
      console.log(
        "[CradleScanner] 🆔 Extracted Cradle ID:",
        this.currentCradleId
      );
      return this.currentCradleId; // ✅ DODANY RETURN
    } else {
      console.log(
        "[CradleScanner] ⚠️ Could not extract Cradle ID from URL:",
        window.location.href
      );
      return null; // ✅ DODANY RETURN
    }
  }

  async checkAutoApplyFilter() {
    const shouldAutoApply = localStorage.getItem("cradle-auto-apply-qa-filter");
    const currentUrl = window.location.href;
    const targetUrl = "https://cradle.egplusww.pl/my-team/";

    console.log("[CradleScanner] Checking auto-apply filter...");
    console.log("[CradleScanner] Should auto-apply:", shouldAutoApply);
    console.log("[CradleScanner] Current URL:", currentUrl);
    console.log("[CradleScanner] Target URL:", targetUrl);

    if (shouldAutoApply === "true") {
      console.log("[CradleScanner] 🔄 Auto-apply flag found!");

      localStorage.removeItem("cradle-auto-apply-qa-filter");

      if (currentUrl !== targetUrl) {
        console.log("[CradleScanner] ❌ Wrong URL for auto-apply, ignoring...");
        return;
      }

      console.log("[CradleScanner] ✅ Correct URL, scheduling auto-apply...");

      setTimeout(async () => {
        console.log("[CradleScanner] 🚀 Starting auto-apply filter...");
        await this.applyQAFilterOnly();
        await this.wait(2000);
        await this.findPendingAsset();
      }, 3000);
    } else {
      console.log("[CradleScanner] No auto-apply flag found");
    }
  }

  // ✅ NOWA METODA - Auto-find asset po powrocie z zajętego asset'a
  async checkAutoFindAsset() {
    const shouldAutoFind = localStorage.getItem("cradle-auto-find-asset");
    const currentUrl = window.location.href;
    const targetUrl = "https://cradle.egplusww.pl/my-team/";

    if (shouldAutoFind === "true" && currentUrl === targetUrl) {
      console.log("[CradleScanner] 🔄 Auto-find asset flag found!");
      localStorage.removeItem("cradle-auto-find-asset");

      // Czekaj na załadowanie strony i automatycznie szukaj asset'a
      setTimeout(async () => {
        console.log(
          "[CradleScanner] 🚀 Auto-searching for next pending asset..."
        );
        this.showNotification(
          "🔍 Automatically searching for next available asset...",
          "info"
        );
        await this.findPendingAsset();
      }, 3000);
    }
  }

  // ✅ NOWA METODA - Automatycznie klika "Take" i pobiera pliki po wejściu w asset
  async checkAutoTakeAsset() {
    const autoTakeId = localStorage.getItem("cradle-auto-take-asset");
    const autoDownloadId = localStorage.getItem("cradle-auto-download-asset");

    // 1. SCENARIUSZ: Pojawiliśmy się tu po "twardym" przeładowaniu strony po kliknięciu Take
    if (autoDownloadId && window.location.href.includes(autoDownloadId)) {
       console.log(`[CradleScanner] 🔄 Auto-download flag found for asset ${autoDownloadId} (Page Reloaded)!`);
       localStorage.removeItem("cradle-auto-download-asset");
       
       // Dajmy stronie 2 sekundy na pełne wyrenderowanie tabelek
       setTimeout(async () => {
           console.log("[CradleScanner] 🚀 Asset taken! Triggering downloads on reloaded page...");
           this.isAutoComparing = true;
           localStorage.setItem("cradle-auto-video-compare", "true");
           await this.downloadFiles();
       }, 2000);
       return;
    }

    // 2. SCENARIUSZ: Dopiero weszliśmy z głównej listy My Team Tasks
    if (autoTakeId && window.location.href.includes(autoTakeId)) {
      console.log(`[CradleScanner] 🔄 Auto-take flag found for asset ${autoTakeId}!`);
      localStorage.removeItem("cradle-auto-take-asset");
      
      // Zabezpieczenie przed przeładowaniem strony:
      localStorage.setItem("cradle-auto-download-asset", autoTakeId);
      
      setTimeout(async () => {
        console.log("[CradleScanner] 🚀 Automatically taking asset...");
        const success = await this.takeAsset();
        
        if (!success) {
           console.log("[CradleScanner] ❌ takeAsset did not succeed (maybe taken by someone else). Passing to next.");
           localStorage.removeItem("cradle-auto-download-asset");
           
           // Powiedz Base Tab żeby wziął następny zadanie i zamknij tę kartę
           localStorage.setItem("cradle-trigger-next", Date.now().toString());
           setTimeout(() => { window.close(); }, 3000);
           return;
        }
        
        // SCENARIUSZ 3: Strona się NIE przeładowała (SPA) - czekamy na zmianę statusu w DOM
        console.log("[CradleScanner] ⏳ Waiting up to 15 seconds for status to change to Processing...");
        let isProcessing = false;
        for (let i = 0; i < 15; i++) {
            await this.wait(1000);
            const currentStatus = this.getCurrentAssetStatus();
            console.log(`[CradleScanner] Status check ${i+1}/15:`, currentStatus);
            if (currentStatus && currentStatus.toLowerCase().includes("processing")) {
                isProcessing = true;
                break;
            }
        }
        
        // Usuwamy flagę zabezpieczającą, bo jesteśmy na bieżąco w tym samym kontekście
        localStorage.removeItem("cradle-auto-download-asset");
        
        if (isProcessing) {
           console.log("[CradleScanner] 🚀 Asset confirmed as Processing! Triggering downloads...");
           this.isAutoComparing = true;
           localStorage.setItem("cradle-auto-video-compare", "true");
           await this.downloadFiles();
           // Do not trigger timeout here. We wait for websocket DOWNLOAD_COMPLETED.
        } else {
           console.log("[CradleScanner] ❌ Timeout waiting for Processing status. Status never changed?");
           this.showNotification("❌ Timeout waiting for Processing status", "error");
        }
      }, 3000);
    }
  }

  async handleCommand(event) {
    console.log("[CradleScanner] Event detail received:", event.detail);
    const action = event.detail?.action;
    console.log("[CradleScanner] Action extracted:", action);

    if (!action) {
      console.error("[CradleScanner] No action found in event detail");
      return;
    }

    switch (action) {
      case "START_AUTOMATION":
        console.log("[CradleScanner] INFO: Rozpoczynam automatyzację...");
        await this.startAutomation();
        break;
      case "STOP_AUTOMATION":
        console.log("[CradleScanner] INFO: Zatrzymuję automatyzację...");
        this.stopAutomation();
        break;
      case "GET_STATUS":
        console.log("[CradleScanner] Current status:", this.status);
        this.showNotification(`Status: ${this.status}`, "info");
        break;
      case "FIND_ASSET":
        console.log("[CradleScanner] INFO: Szukam wolnego assetu...");
        await this.findPendingAsset();
        break;
      case "TAKE_ASSET":
        console.log("[CradleScanner] INFO: Przejmuję asset...");
        await this.takeAsset();
        break;
      case "DOWNLOAD_FILES":
        console.log("[CradleScanner] INFO: Rozpoczynam pobieranie plików...");
        await this.downloadFiles();
        break;
      case "VIDEO_COMPARE":
        console.log("[CradleScanner] INFO: Starting Video Compare...");
        await this.startVideoCompare(event.detail?.data);
        break;
      default:
        console.log("[CradleScanner] Unknown command:", action);
    }
  }
  
  stopAutomation() {
    console.log("[CradleScanner] Stopping automation...");
    localStorage.removeItem("cradle-auto-find-asset");
    localStorage.removeItem("cradle-auto-apply-qa-filter");
    localStorage.removeItem("cradle-auto-take-asset");
    localStorage.removeItem("cradle-auto-download-asset");
    
    // Zapobiegaj triggerowaniu kolejnych zdarzeń
    localStorage.setItem("cradle-automation-stopped", "true");
    localStorage.removeItem("cradle-auto-video-compare");
    
    this.isAutoComparing = false;
    this.isScanning = false;
    this.status = "Automation stopped";
    this.showNotification("⏹️ Automation stopped", "info");
    setTimeout(() => {
        window.location.reload();
    }, 1500);
  }

  sendStatus() {
    console.log("[CradleScanner] Current status:", this.status);
    document.dispatchEvent(
      new CustomEvent("extension-response", {
        detail: {
          action: "STATUS_UPDATE",
          data: { status: this.status, isScanning: this.isScanning },
        },
      })
    );
  }

  showNotification(message, type = "info") {
    console.log(`[CradleScanner] ${type.toUpperCase()}: ${message}`);
    document.dispatchEvent(
      new CustomEvent("extension-notification", {
        detail: { message, type },
      })
    );
  }

  async startAutomation() {
    const targetUrl = "https://cradle.egplusww.pl/my-team/";
    const currentUrl = window.location.href;

    console.log("[CradleScanner] Starting automation...");
    console.log("[CradleScanner] Current URL:", currentUrl);
    console.log("[CradleScanner] Target URL:", targetUrl);
    
    localStorage.removeItem("cradle-automation-stopped");

    if (currentUrl !== targetUrl) {
      console.log("[CradleScanner] ❌ Wrong page! Redirecting...");

      localStorage.setItem("cradle-auto-apply-qa-filter", "true");
      console.log("[CradleScanner] ✅ Auto-apply flag set in localStorage");

      this.status = "Redirecting to My Team Tasks...";
      this.showNotification(
        "Redirecting to My Team Tasks - filter will be applied automatically",
        "info"
      );

      setTimeout(() => {
        console.log("[CradleScanner] 🔄 Redirecting now...");
        window.location.href = targetUrl;
      }, 1000);

      return;
    }

    console.log(
      "[CradleScanner] ✅ Already on correct page, applying filter..."
    );
    await this.applyQAFilterOnly();
    await this.wait(2000);
    await this.findPendingAsset();
  }

  async findPendingAsset() {
    console.log("[CradleScanner] 🔍 Finding pending asset...");
    this.status = "Finding pending asset...";
    this.showNotification("Searching for pending assets...", "info");

    try {
      const allTables = document.querySelectorAll("table");
      console.log(`[CradleScanner] Found ${allTables.length} tables on page`);

      let assetsTable = null;

      for (let i = 0; i < allTables.length; i++) {
        const table = allTables[i];
        const rows = table.querySelectorAll("tr");
        const dataRows = Array.from(table.querySelectorAll("tr")).filter(
          (row) => row.querySelectorAll("td").length > 0
        );

        console.log(`[CradleScanner] === TABLE ${i} ANALYSIS ===`);
        console.log(
          `[CradleScanner] Table ${i}: ${rows.length} total rows, ${dataRows.length} data rows`
        );
        console.log(`[CradleScanner] Table ${i} classes:`, table.className);
        console.log(`[CradleScanner] Table ${i} id:`, table.id);

        if (dataRows.length > 0) {
          console.log(`[CradleScanner] Table ${i} - First 3 rows content:`);
          for (let j = 0; j < Math.min(3, dataRows.length); j++) {
            const row = dataRows[j];
            const cells = row.querySelectorAll("td");
            const rowContent = Array.from(cells)
              .slice(0, 5)
              .map((cell) => `"${cell.textContent.trim()}"`)
              .join(" | ");
            console.log(`[CradleScanner] Table ${i} Row ${j}: ${rowContent}`);
          }
        } else {
          console.log(`[CradleScanner] Table ${i} has no data rows`);
        }

        if (dataRows.length > 0) {
          const firstDataRow = dataRows[0];
          const firstCell = firstDataRow.querySelector("td");

          if (firstCell) {
            const cellText = firstCell.textContent.trim();
            console.log(`[CladleScanner] Table ${i} first cell: "${cellText}"`);
            console.log(
              `[CradleScanner] Table ${i} is pure number: ${/^\d+$/.test(
                cellText
              )}`
            );
            console.log(
              `[CradleScanner] Table ${i} is 6+ digit number: ${/^\d{6,}$/.test(
                cellText
              )}`
            );
            console.log(
              `[CradleScanner] Table ${i} contains numbers: ${/\d+/.test(
                cellText
              )}`
            );

            if (/^\d+$/.test(cellText)) {
              console.log(
                `[CradleScanner] ✅ Found assets table (Table ${i}) with pure number Cradle.ID: ${cellText}`
              );
              assetsTable = table;
              break;
            } else if (/^\d{6,}$/.test(cellText)) {
              console.log(
                `[CradleScanner] ✅ Found assets table (Table ${i}) with 6+ digit Cradle.ID: ${cellText}`
              );
              assetsTable = table;
              break;
            } else if (
              cellText.includes("891") ||
              cellText.includes("892") ||
              cellText.includes("878")
            ) {
              console.log(
                `[CradleScanner] ✅ Found assets table (Table ${i}) with known Cradle.ID pattern: ${cellText}`
              );
              assetsTable = table;
              break;
            }
          }
        }
        console.log(`[CradleScanner] === END TABLE ${i} ANALYSIS ===`);
      }

      if (!assetsTable) {
        console.log("[CradleScanner] ❌ No assets table found. Summary:");
        for (let i = 0; i < allTables.length; i++) {
          const table = allTables[i];
          const dataRows = Array.from(table.querySelectorAll("tr")).filter(
            (row) => row.querySelectorAll("td").length > 0
          );
          const firstCellText =
            dataRows.length > 0
              ? dataRows[0].querySelector("td")?.textContent.trim()
              : "N/A";
          console.log(
            `[CradleScanner] Table ${i}: ${dataRows.length} rows, first cell: "${firstCellText}"`
          );
        }

        throw new Error(
          `Assets table not found among ${allTables.length} tables. No table has Cradle.ID format in first column.`
        );
      }

      console.log(
        "[CradleScanner] ✅ Using assets table, waiting for data to load..."
      );

      let rows = [];
      let attempts = 0;
      const maxAttempts = 20;

      while (rows.length === 0 && attempts < maxAttempts) {
        rows = Array.from(assetsTable.querySelectorAll("tbody tr"));

        if (rows.length === 0) {
          rows = Array.from(assetsTable.querySelectorAll("tr")).filter(
            (row) => {
              const cells = row.querySelectorAll("td");
              return cells.length > 0;
            }
          );
        }

        if (rows.length === 0) {
          console.log(
            `[CradleScanner] Attempt ${
              attempts + 1
            }: No rows in assets table, waiting...`
          );
          await this.wait(500);
          attempts++;
        } else {
          console.log(
            `[CradleScanner] Success! Found ${rows.length} rows in assets table`
          );
          break;
        }
      }

      if (rows.length === 0) {
        throw new Error("No data rows found in assets table after waiting");
      }

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const cells = row.querySelectorAll("td");

        if (cells.length === 0) continue;

        const cradleId = cells[0].textContent.trim();

        const stateCell = cells[cells.length - 1];
        const stateButton = stateCell.querySelector("button .mj-button-txt");
        const state = stateButton
          ? stateButton.textContent.trim().toLowerCase()
          : "";

        console.log(
          `[CradleScanner] Row ${i}: Cradle.ID=${cradleId}, State="${state}"`
        );

        if (state.includes("processing")) {
          console.log(
            `[CradleScanner] Skipping ${cradleId} - already processing`
          );
          continue;
        }

        if (state.includes("pending")) {
          const assetUrl = `https://cradle.egplusww.pl/assets/deliverable-details/${cradleId}/comments/`;

          // Extract client name from Client column (index 4 in the table)
          const clientName = cells.length > 4 ? cells[4].textContent.trim() : null;
          if (clientName) {
            localStorage.setItem("cradle-current-client", clientName);
            console.log(`[CradleScanner] 🏢 Client detected: ${clientName}`);
          }

          console.log(
            `[CradleScanner] ✅ Found earliest pending asset: ${cradleId}`
          );
          console.log(`[CradleScanner] Opening URL: ${assetUrl}`);

          this.status = `Opening asset ${cradleId}`;
          this.showNotification(
            `✅ Opening pending asset ${cradleId} (${clientName || 'Unknown client'})...`,
            "success"
          );

          // Set flag so next page knows to auto-take it
          localStorage.setItem("cradle-auto-take-asset", cradleId);
          window.open(assetUrl, "_blank");

          this.status = "Monitoring asset tab...";
          this.showNotification(`Asset ${cradleId} opened in new tab. Waiting...`, "info");
          return;
        }
      }

      this.status = "No pending assets found";
      this.showNotification(
        "❌ No pending assets available for processing",
        "warning"
      );
      console.log(
        "[CradleScanner] No pending assets found - all are either processing or completed"
      );
      
      console.log("[CradleScanner] ⏳ Waiting 120 seconds before reload...");
      this.status = "Waiting 2 minutes...";
      this.showNotification("⏳ No pending assets. Auto-retry in 2 minutes...", "info");
      
      // Send log to dashboard
      try {
        chrome.runtime.sendMessage({
          action: "LOG_TO_DASHBOARD",
          payload: {
            component: "extension",
            action: "FIND_ASSET",
            message: "No pending assets found. Waiting 2 minutes for new tasks.",
            is_error: false
          }
        });
      } catch(e) {}

      setTimeout(() => {
        localStorage.setItem("cradle-auto-find-asset", "true");
        window.location.reload();
      }, 120000);

    } catch (error) {
      console.error("[CradleScanner] Error finding pending asset:", error);
      this.status = `Error: ${error.message}`;
      this.showNotification(`❌ Error: ${error.message}`, "error");

      // Send log to dashboard
      try {
        chrome.runtime.sendMessage({
          action: "LOG_TO_DASHBOARD",
          payload: {
            component: "extension",
            action: "FIND_ASSET",
            message: error.message,
            is_error: true
          }
        });
      } catch(e) {}

      // Do not block with alert, wait 2 mins and try again
      console.log("[CradleScanner] ⏳ Error occurred. Waiting 120 seconds before reload...");
      this.showNotification("⏳ Waiting 2 minutes to retry after error...", "warning");
      setTimeout(() => {
        localStorage.setItem("cradle-auto-find-asset", "true");
        window.location.reload();
      }, 120000);
    }
  }

  // ✅ POPRAWIONA METODA takeAsset() z fallback logiką
  async takeAsset() {
    console.log("[CradleScanner] 🎯 Taking asset...");
    this.status = "Taking asset...";
    this.showNotification("Taking asset...", "info");

    try {
      // ✅ KROK 1: Sprawdź obecny status
      const currentStatus = this.getCurrentAssetStatus();
      console.log("[CradleScanner] Current asset status:", currentStatus);

      if (currentStatus && currentStatus.toLowerCase().includes("processing")) {
        // ❌ KTOŚ INNY WZIĄŁ ASSET W MIĘDZYCZASIE!
        console.log(
          "[CradleScanner] ❌ Asset was taken by someone else - going back to find another one"
        );
        this.status = "Asset taken by someone else, searching for next...";
        this.showNotification("❌ Asset taken by someone else!", "warning");
        this.showNotification("🔄 Returning to My Team Tasks...", "info");

        // Zamknij obecne okno po krótkim opóźnieniu
        setTimeout(() => {
          window.close(); // Zamknij obecną zakładkę
        }, 2000);

        // Jeśli okno się nie zamknie (główna zakładka), przekieruj
        setTimeout(() => {
          console.log("[CradleScanner] 🔄 Redirecting to My Team Tasks...");
          window.location.href = "https://cradle.egplusww.pl/my-team/";

          // Ustaw flagę żeby automatycznie szukać kolejnego asset'a
          localStorage.setItem("cradle-auto-find-asset", "true");
        }, 3000);

        return false;
      }

      if (currentStatus && currentStatus.toLowerCase().includes("pending")) {
        // ✅ Asset jest wolny - można go wziąć!
        console.log("[CradleScanner] ✅ Asset is Pending - attempting to take");
      } else {
        console.log(
          "[CradleScanner] ⚠️ Unclear status, attempting to take anyway"
        );
      }

      // ✅ KROK 2: Szukaj przycisku "Pending" (stanu asset'a)
      const pendingButtons = document.querySelectorAll(
        "button.btn-state .mj-button-txt"
      );
      let pendingButton = null;

      for (const button of pendingButtons) {
        const buttonText = button.textContent.trim().toLowerCase();
        if (buttonText.includes("pending")) {
          pendingButton = button.closest("button");
          console.log("[CradleScanner] Found Pending state button");
          break;
        }
      }

      if (!pendingButton) {
        // Nie ma przycisku "Pending" - prawdopodobnie status się zmienił
        console.log(
          "[CradleScanner] ❌ No Pending button found - asset may have been taken"
        );

        // Sprawdź status ponownie
        const newStatus = this.getCurrentAssetStatus();
        if (newStatus && newStatus.toLowerCase().includes("processing")) {
          // Potwierdzone - asset został wzięty
          this.showNotification(
            "❌ Asset was just taken by someone else!",
            "error"
          );
          this.showNotification(
            "🔄 Going back to find another asset...",
            "info"
          );

          setTimeout(() => {
            window.close();
          }, 2000);

          setTimeout(() => {
            window.location.href = "https://cradle.egplusww.pl/my-team/";
            localStorage.setItem("cradle-auto-find-asset", "true");
          }, 3000);

          return false;
        }

        throw new Error(
          "Pending button not found - asset may not be available"
        );
      }

      // ✅ KROK 3: Kliknij "Pending"
      console.log("[CradleScanner] Clicking Pending button...");
      pendingButton.click();

      console.log("[CradleScanner] Waiting for Take popup...");
      await this.wait(1500);

      // ✅ KROK 4: Szukaj przycisku "Take" w popup
      const takeButtons = document.querySelectorAll(
        "button.btn-success, button"
      );
      let takeButton = null;

      for (const button of takeButtons) {
        const buttonText = button.textContent.trim().toLowerCase();
        if (buttonText.includes("take")) {
          takeButton = button;
          console.log("[CradleScanner] Found Take button");
          break;
        }
      }

      if (!takeButton) {
        // Brak przycisku "Take" - asset został wzięty między kliknięciem "Pending" a otwarciem popup
        console.log(
          "[CradleScanner] ❌ Take button not found - asset taken during popup opening"
        );
        this.showNotification("❌ Asset taken while opening popup!", "error");
        this.showNotification("🔄 Searching for another asset...", "info");

        setTimeout(() => {
          window.close();
        }, 2000);

        setTimeout(() => {
          window.location.href = "https://cradle.egplusww.pl/my-team/";
          localStorage.setItem("cradle-auto-find-asset", "true");
        }, 3000);

        return false;
      }

      // ✅ KROK 5: Kliknij "Take"
      console.log("[CradleScanner] Clicking Take button...");
      takeButton.click();

      console.log("[CradleScanner] Waiting for status change...");
      await this.wait(2000);

      // ✅ SUKCES!
      this.status = "Asset taken successfully";
      this.showNotification("✅ Asset taken! Status: Processing", "success");
      this.showNotification("📁 Ready to download files...", "info");

      console.log(
        "[CradleScanner] ✅ Asset taken successfully - now Processing"
      );
      return true;
    } catch (error) {
      console.error("[CradleScanner] Error taking asset:", error);
      this.status = `Error: ${error.message}`;
      this.showNotification(`❌ Error: ${error.message}`, "error");
      return false;
    }
  }

  // ✅ NOVA METODA: Sprawdza obecny status asset'a
  getCurrentAssetStatus() {
    try {
      // Szukaj w różnych miejscach na stronie
      const statusElements = document.querySelectorAll(
        '[class*="status"], [class*="state"], .mj-button-txt'
      );

      for (const element of statusElements) {
        const text = element.textContent.trim();
        if (
          text &&
          (text.toLowerCase().includes("pending") ||
            text.toLowerCase().includes("processing") ||
            text.toLowerCase().includes("completed"))
        ) {
          return text;
        }
      }

      return null;
    } catch (error) {
      console.log("[CradleScanner] Error getting status:", error);
      return null;
    }
  }

  async downloadFiles() {
    console.log("=== ROZPOCZYNAM POBIERANIE PLIKÓW ===");

    const cradleId = this.extractCradleId();
    console.log("Cradle ID:", cradleId);

    if (!cradleId) {
      this.showNotification("Nie można pobrać Cradle ID z URL", "error");
      return;
    }

    // Find and scan the asset comments tables - TUTAJ JEST KLUCZOWA ZMIANA
    let tables = [];
    if (window.location.href.includes("/assets/deliverable-details/")) {
       tables = await this.findAssetCommentsTables();
    }

    // ✅ DODAJ DEBUGOWANIE
    console.log("[CradleScanner] 🔍 DEBUG: Tables received in downloadFiles:", tables?.length);

    const fileInfo = await this.scanForFiles(tables);

    console.log("=== WYNIKI SKANOWANIA PLIKÓW ===");
    console.log("Pełne fileInfo:", fileInfo);

    // Download acceptance file if found
    if (fileInfo.acceptanceFile) {
      console.log("✓ ZNALEZIONO PLIK AKCEPTACJI:");
      console.log("  - Nazwa:", fileInfo.acceptanceFile.name);
      console.log("  - URL:", fileInfo.acceptanceFile.url);
      console.log("  - Rząd:", fileInfo.acceptanceFile.row);

      // Pass the name as preferredFilename (if found in UI text)
      // Do NOT default to "acceptance.mp4" to avoid unwanted renaming
      const filename = fileInfo.acceptanceFile.name;
      await this.handleAcceptanceFile(fileInfo.acceptanceFile, cradleId, filename); 
    } else {
      console.log("✗ PLIK AKCEPTACJI NIE ZNALEZIONY");
    }

    // Handle emission file
    if (fileInfo.emissionFile) {
      console.log("✓ ZNALEZIONO PLIK EMISJI:");
      console.log("  - Typ:", fileInfo.emissionFile.type);
      if (fileInfo.emissionFile.filename) {
        console.log("  - Nazwa:", fileInfo.emissionFile.filename);
        console.log("  - URL:", fileInfo.emissionFile.url);
      }
      if (fileInfo.emissionFile.path) {
        console.log("  - Ścieżka:", fileInfo.emissionFile.path);
      }
      console.log("  - Rząd:", fileInfo.emissionFile.row);

      await this.handleEmissionFile(
        fileInfo.emissionFile,
        cradleId,
        fileInfo.acceptanceFile?.name // Przekaż nazwę acceptance dla porównania
      );
    } else {
      console.log("✗ PLIK EMISJI NIE ZNALEZIONY");
    }

    console.log("=== KONIEC WYNIKÓW SKANOWANIA ===");

    // Show completion message
    if (!fileInfo.acceptanceFile && !fileInfo.emissionFile) {
      console.log("Brak pliku akceptacji do pobrania");
      this.showNotification("Nie znaleziono plików do pobrania", "warning");
    } else if (!fileInfo.acceptanceFile) {
      console.log("Brak pliku akceptacji do pobrania");
      this.showNotification("Pobrano tylko plik emisji", "warning");
    } else if (!fileInfo.emissionFile) {
      console.log("Brak pliku emisji do pobrania");
      this.showNotification("Pobrano tylko plik akceptacji", "warning");
    } else {
      this.showNotification("Pobrano oba pliki pomyślnie", "success");
    }
    // Wyślij info o pobranych plikach do Desktop App

    // Wyślij info o pobranych plikach do Desktop App
    console.log("[CradleScanner] 📤 Sending files info to Desktop App...");
    
    // CRITICAL FIX: Only send network paths to Desktop App.
    // Attachments are handled by Extension. Desktop App shouldn't try to download them without auth.
    const { templateId, jobNumber, langCode } = this.extractAssetMetadata();
    const filesData = {
      action: "FILES_DETECTED",
      cradleId: this.currentCradleId,
      templateId: templateId,
      jobNumber: jobNumber,
      langCode: langCode,
      acceptanceFile: fileInfo.acceptanceFile?.type === "network_path" ? fileInfo.acceptanceFile : null,
      emissionFile: fileInfo.emissionFile?.type === "network_path" ? fileInfo.emissionFile : null,
      timestamp: Date.now(),
    };

    const sent = desktopConnection.sendMessage(filesData);
    console.log("[CradleScanner] Files data sent to Desktop App:", sent);

    if (sent) {
      this.showNotification("📤 Files info sent to Desktop App", "info");
    } else {
      this.showNotification("❌ Desktop App not connected", "warning");
    }
  }

  async findAssetCommentsTables() {
    console.log("[CradleScanner] 🔍 Looking for Asset comments tables...");

    const maxAttempts = 10;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      console.log(
        `[CradleScanner] ⏳ Table search attempt ${attempt}/${maxAttempts}`
      );

      const tables = document.querySelectorAll("table");
      console.log(`[CradleScanner] Found ${tables.length} tables on page`);

      const matchedTables = [];
      for (let table of tables) {
        let isMatch = false;
        // Method 1: Check for "Asset comments" or "Comment" in headers
        const headers = table.querySelectorAll("th");
        for (let header of headers) {
          const headerText = header.textContent.trim().toLowerCase();
          if (
            headerText.includes("asset comments") ||
            headerText.includes("comment") ||
            headerText.includes("attachment")
          ) {
            console.log(`[CradleScanner] ✅ Found table via header: ${headerText}`);
            matchedTables.push(table);
            isMatch = true;
            break;
          }
        }

        if (isMatch) continue;

        // Method 2: Check for key phrases in any cell
        const cells = table.querySelectorAll("td, th");
        for (let cell of cells) {
          const cellText = cell.textContent.trim().toLowerCase();
          if (
            cellText.includes("proofreading") ||
            cellText.includes("final file preparation") ||
            cellText.includes("broadcast preparation") ||
            cellText.includes("file preparation")
          ) {
            console.log(`[CradleScanner] ✅ Found table via content: ${cellText}`);
            matchedTables.push(table);
            break;
          }
        }
      }

      if (matchedTables.length > 0) {
          console.log(`[CradleScanner] ✅ Returning ${matchedTables.length} tables in total`);
          return matchedTables;
      }

      if (attempt < maxAttempts) {
        console.log(
          `[CradleScanner] ⏳ Table not found, waiting 1 second... (${attempt}/${maxAttempts})`
        );
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }

    console.log("[CradleScanner] ❌ Asset comments tables not found after all attempts");
    return [];
  }

  async scanForFiles(tables) {
    console.log("[CradleScanner] 🔍 Starting smart file scan...");

    let fileInfo = { emissionFile: null, acceptanceFile: null };
    const tableArray = Array.isArray(tables) ? tables : (tables ? [tables] : []);

    // 1. Scan current page tables
    for (const tbl of tableArray) {
        const partial = this.scanTableForFiles(tbl);
        if (partial.emissionFile && !fileInfo.emissionFile) fileInfo.emissionFile = partial.emissionFile;
        if (partial.acceptanceFile && !fileInfo.acceptanceFile) fileInfo.acceptanceFile = partial.acceptanceFile;
    }

    // 2. Recursive Scan: If Acceptance missing, look for links in "distribution" rows
    if (!fileInfo.acceptanceFile) {
      console.log(
        "[CradleScanner] ⚠️ Acceptance file not found. checking for linked assets..."
      );
      
      let linkedAssetUrl = null;
      for (const tbl of tableArray) {
          linkedAssetUrl = this.findLinkedAssetUrl(tbl);
          if (linkedAssetUrl) break;
      }

      if (linkedAssetUrl) {
        console.log(
          "[CradleScanner] 🔗 Found linked asset URL:",
          linkedAssetUrl
        );
        this.showNotification("🔗 Checking linked asset for files...", "info");

        const linkedTable = await this.fetchAndParseLinkedAsset(linkedAssetUrl);
        if (linkedTable) {
          console.log("[CradleScanner] 📄 Scanning linked asset table...");
          const linkedFileInfo = this.scanTableForFiles(linkedTable);

          if (linkedFileInfo.acceptanceFile) {
            console.log(
              "[CradleScanner] ✅ Found Acceptance in linked asset!"
            );
            fileInfo.acceptanceFile = linkedFileInfo.acceptanceFile;
          }
          // Optional: Check emission in linked asset too? Usually not needed but safe to check
          if (!fileInfo.emissionFile && linkedFileInfo.emissionFile) {
             console.log("[CradleScanner] ✅ Found Emission in linked asset!");
             fileInfo.emissionFile = linkedFileInfo.emissionFile;
          }
        }
      }
    }

    // 3. Final Summary
    console.log("[CradleScanner] 📋 === FINAL SCAN RESULTS ===");
    console.log(
      "[CradleScanner] - Acceptance:",
      fileInfo.acceptanceFile ? "✅ FOUND" : "❌ MISSING"
    );
    console.log(
      "[CradleScanner] - Emission:",
      fileInfo.emissionFile ? "✅ FOUND" : "❌ MISSING"
    );

    return fileInfo;
  }

  findLinkedAssetUrl(table) {
    const rows = table.querySelectorAll("tr");
    for (const row of rows) {
      const text = row.textContent.toLowerCase();
      // Look for rows like "Peugeot...VIDEO: pm distribution" or "final file preparation"
      if (text.includes("distribution") || text.includes("final file")) {
        console.log(`[CradleScanner] 🔎 Checking row for links: "${text.substring(0, 50)}..."`);
        console.log("[CradleScanner] 📄 Row HTML:", row.innerHTML);

        // Check for links in comments - broader check
        const links = row.querySelectorAll("a");
        for (const link of links) {
             const href = link.getAttribute("href");
             if (!href) continue;

             // Exclude self-link, mailto, etc.
             if (href.includes(this.currentCradleId) || href.startsWith("mailto:") || href === "#") {
                 continue;
             }

             // Valid asset link usually contains /assets/ or /deliverable-details/
             if (href.includes("/assets/") || href.includes("deliverable-details")) {
                 console.log(`[CradleScanner] 🔗 Found potential linked asset (<a>): ${href}`);
                 return link.href; // Return absolute URL
             }
        }

        // FALLBACK: Look for plain text URLs if no <a> tag matched
        // FIX: Replace HTML tags (like <br>) with spaces, so words don't concatenate into the URL
        const htmlWithSpaces = row.innerHTML.replace(/<[^>]+>/g, ' ');
        // Regex: stop at whitespace/newline so we don't capture trailing text
        const urlRegex = /https:\/\/[^\s"'<>]+\/assets\/deliverable-details\/(\d+)(?:\/[^\s"'<>]*)?/i;
        const match = htmlWithSpaces.match(urlRegex);

        if (match) {
            // Strip any trailing non-path chars (e.g. punctuation)
            const foundUrl = match[0].replace(/[.,;!?]+$/, "");
            console.log(`[CradleScanner] 🔗 Found potential linked asset (text): ${foundUrl}`);
            return foundUrl;
        }
      }
    }
    return null;
  }

  // ✅ New helper: Fetch and parse external Cradle page
  async fetchAndParseLinkedAsset(url) {
      try {
          console.log(`[CradleScanner] 🌍 Fetching linked asset: ${url}`);
          const response = await fetch(url);
          const html = await response.text();
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, "text/html");
          
          // Reuse existing table finder logic, but on the new doc
          // We need to reimplement a simple version of findAssetCommentsTable for a DOC
          const tables = doc.querySelectorAll("table");
          for (const table of tables) {
              if (table.textContent.toLowerCase().includes("asset comments") || 
                  table.textContent.toLowerCase().includes("comment")) {
                  return table;
              }
          }
          return null;
      } catch (e) {
          console.error("[CradleScanner] ❌ Error fetching linked asset:", e);
          return null;
      }
  }

  // ✅ Reusable scanner logic (Logic extracted from original scanForFiles)
  scanTableForFiles(table) {
    console.log("[CradleScanner] 🔍 Scanning table rows...");
    const fileInfo = { emissionFile: null, acceptanceFile: null };

    if (!table) return fileInfo;

    const rows = table.querySelectorAll("tbody tr");
    const scanRows = rows.length > 0 ? rows : table.querySelectorAll("tr");

    for (let i = 0; i < scanRows.length; i++) {
        const row = scanRows[i];
        const cells = row.querySelectorAll("td");
        if (cells.length === 0) continue;

        const firstCellText = cells[0].textContent.toLowerCase().trim();

        // 1. EMISSION — Broadcast & Final file preparation = delivery/emission files
        if (firstCellText.includes("broadcast file preparation")) {
            console.log(`[CradleScanner] 📡 Row ${i}: 'broadcast file preparation' → EMISSION`);
            this.extractEmissionFromRow(row, fileInfo, i);
        }

        else if (firstCellText.includes("final file preparation")) {
            console.log(`[CradleScanner] 📡 Row ${i}: 'final file preparation' → EMISSION`);
            this.extractEmissionFromRow(row, fileInfo, i);
        }

        // 2. ACCEPTANCE — video preparation (primary)
        else if (firstCellText.includes("video preparation")) {
            this.extractAcceptanceFromRow(row, fileInfo, i);
        }

        // 3. ACCEPTANCE — pm approval (above qa proofreading)
        else if (firstCellText.includes("pm approval") && !fileInfo.acceptanceFile) {
            this.extractAcceptanceFromRow(row, fileInfo, i);
        }

        // 4. ACCEPTANCE — generic file preparation (NOT final/broadcast — excluded above)
        else if (firstCellText.includes("file preparation")) {
            this.extractAcceptanceFromRow(row, fileInfo, i);
        }

        // 5. ACCEPTANCE — QA Proofreading fallback
        else if (firstCellText.includes("proofreading") && !fileInfo.acceptanceFile) {
             this.extractAcceptanceFromRow(row, fileInfo, i);
        }

    }
    return fileInfo;
  }

  extractEmissionFromRow(row, fileInfo, rowIndex) {
      if (fileInfo.emissionFile) return; // Already found

      console.log(`[CradleScanner] 🔍 extractEmissionFromRow called for row ${rowIndex}`);
      const cells = row.querySelectorAll("td");
      for (const cell of cells) {
          if (fileInfo.emissionFile) return; // Already found, stop scanning

          const text = cell.textContent.trim();

          // Debug: log all href links in cell
          const allLinks = [...cell.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
          if (allLinks.length) console.log(`[CradleScanner] 🔗 Row ${rowIndex} cell links:`, allLinks);
          
          // A. Network Paths
          const lucidLinkEl = cell.querySelector('a[href^="lucid://"]');
          const hasNetworkContent = text.includes("/Volumes/") || text.includes("lucid://") || text.includes("\\\\") || lucidLinkEl;

          if (hasNetworkContent) {
              console.log(`[CradleScanner] 🌐 Found potential network path in row ${rowIndex}`);

              let cleanPath = null;
              let lucidFilespace = null;

              // 1. Prefer explicit /Volumes/ path in text
              if (text.includes("/Volumes/")) {
                  const match = text.match(/\/Volumes\/[^\n\r"'`<>]+/);
                  if (match) cleanPath = match[0].trim().replace(/['\s]+$/, '');

              // 2. Handle lucid:// — via <a href> tag (most reliable)
              } else if (lucidLinkEl) {
                  const lucidHref = lucidLinkEl.getAttribute("href"); // e.g. lucid://alfa.egpluswarsaw/file/393:20108/EML
                  const lucidMatch = lucidHref.match(/^lucid:\/\/([^/]+)/);
                  if (lucidMatch) {
                      lucidFilespace = lucidMatch[1]; // "alfa.egpluswarsaw"
                      console.log(`[CradleScanner] 🔗 lucid:// filespace: ${lucidFilespace}`);
                      // Desktop App will resolve using filespace + job number + template ID
                      cleanPath = `__lucid__`; // Sentinel — Desktop App handles actual path
                  }

              // 3. Fallback: lucid:// in raw text
              } else if (text.includes("lucid://")) {
                  const lucidMatch = text.match(/lucid:\/\/([^/\s"'<>]+)/);
                  if (lucidMatch) {
                      lucidFilespace = lucidMatch[1];
                      console.log(`[CradleScanner] 🔗 lucid:// filespace (text): ${lucidFilespace}`);
                      cleanPath = `__lucid__`;
                  }
              }

              if (cleanPath) {
                  fileInfo.emissionFile = {
                      type: "network_path",
                      path: cleanPath,
                      lucidFilespace: lucidFilespace || null,
                      name: "emission_network",
                      row: rowIndex
                  };
                  console.log(`[CradleScanner] ✅ Found Network Emission (filespace: ${lucidFilespace || 'direct path'})`);
                  return;
              }
          }

          // B. Attachments - prefer direct /media/ URLs, also handle fa-file icon links
          const link = cell.querySelector('a[href^="/media/cradle/comment/"]') || 
                       cell.querySelector('a[href*="/media/cradle/"]') ||
                       cell.querySelector("a i.fa-file")?.parentElement;
          
          if (link && link.href) {
               // Skip nc-download links (they are API endpoints, not direct files)
               if (link.href.includes("nc-download")) {
                   console.log(`[CradleScanner] ⛔ Skipping nc-download in emission row ${rowIndex}: ${link.href}`);
                   continue;
               }
               
               const fullUrl = link.href.startsWith("http") ? link.href : `https://cradle.egplusww.pl${link.href}`;

               // Try to get filename from text content (same logic as extractAcceptanceFromRow)
               const cleanUrl = fullUrl.endsWith("/") ? fullUrl.slice(0, -1) : fullUrl;
               let filename = cleanUrl.split("/").pop();
               const textContent = link.parentElement?.textContent?.trim();
               if (textContent && textContent.includes(".")) {
                   filename = textContent;
               }
               if (!filename || filename.length < 3) {
                   filename = "emission.mp4";
               }
               
               // Only accept video files and ZIPs
               const validExts = [".mp4", ".mov", ".mxf", ".zip"];
               const ext = filename.toLowerCase().match(/\.[^.]+$/)?.[0] || "";
               if (!validExts.includes(ext)) {
                   console.log(`[CradleScanner] ⏩ Skipping non-video emission: ${filename}`);
                   continue;
               }
               
               fileInfo.emissionFile = {
                   type: "attachment",
                   url: fullUrl,
                   name: filename,
                   row: rowIndex
               };
               console.log(`[CradleScanner] ✅ Found Attachment Emission: ${fileInfo.emissionFile.name}`);
               return; // Stop after first valid match
          }

      }
  }

  extractAcceptanceFromRow(row, fileInfo, rowIndex) {
      if (fileInfo.acceptanceFile) return;

    const cells = row.querySelectorAll("td");
    
    // Use for...of to allow breaking
    for (const cell of cells) {
        if (fileInfo.acceptanceFile) break; // Double check

        const link = cell.querySelector('a[href^="/media/cradle/comment/"]') || 
                     cell.querySelector("a i.fa-file")?.parentElement;
        
        if (link && link.href) {
             const fullUrl = link.href.startsWith("http") ? link.href : `https://cradle.egplusww.pl${link.href}`;
             
             // Try to get filename from text content if URL doesn't have it
             // Clean URL of trailing slash for better pop()
             const cleanUrl = fullUrl.endsWith("/") ? fullUrl.slice(0, -1) : fullUrl;
             let filename = cleanUrl.split("/").pop();

             const textContent = link.parentElement.textContent.trim();
             if (textContent.includes(".")) {
                 filename = textContent;
             }

             // Final fallback if filename is empty, just an ID, or misses an extension entirely
             if (!filename || filename.length < 3 || !filename.includes(".")) {
                  filename = (filename && filename.length >= 3) ? `${filename}.mp4` : "acceptance.mp4"; 
             }

             // Only accept video files and ZIPs
             const validExts = [".mp4", ".mov", ".mxf", ".zip"];
             const ext = filename.toLowerCase().match(/\.[^.]+$/)?.[0] || "";
             if (!validExts.includes(ext)) {
                 console.log(`[CradleScanner] ⏩ Skipping non-video acceptance: ${filename}`);
                 continue;
             }

             fileInfo.acceptanceFile = {
                 type: "attachment",
                 url: fullUrl,
                 name: filename,
                 row: rowIndex
             };
             console.log(`[CradleScanner] ✅ Found Acceptance: ${fileInfo.acceptanceFile.name}`);
             return; // Stop matching in this row after finding one
        }
    }
  }

  // ✅ UNIVERSAL FILE DOWNLOAD
  // Tries chrome.downloads first (supports subdirectories), falls back to fetch+blob
  async downloadViaFetch(url, downloadPath) {
    const displayName = downloadPath.split('/').pop();
    console.log(`[CradleScanner] ⬇️ Downloading: ${downloadPath}`);

    // 1. Try Chrome Downloads API (supports saving to subdirectories)
    try {
      if (chrome?.runtime?.sendMessage) {
        const result = await new Promise((resolve) => {
          chrome.runtime.sendMessage(
            { action: "DOWNLOAD_FILE", url, filename: downloadPath },
            (response) => {
              if (chrome.runtime.lastError) {
                console.warn("[CradleScanner] Chrome API error:", chrome.runtime.lastError.message);
                resolve(false);
              } else {
                resolve(response?.success !== false);
              }
            }
          );
        });
        if (result) {
          console.log(`[CradleScanner] ✅ Chrome download started: ${downloadPath}`);
          return true;
        }
      }
    } catch (e) {
      console.warn("[CradleScanner] Chrome API unavailable, using fetch fallback");
    }

    // 2. Fallback: fetch + blob + ask Desktop App to move file
    const cradleId = downloadPath.includes('/') ? downloadPath.split('/')[0] : null;
    console.log(`[CradleScanner] ⬇️ Fallback: fetching ${displayName}... Chrome downloads failed!`);
    
    try {
      const response = await fetch(url, { credentials: 'include' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      // OOM PROTECTION: If file is > 1.5 GB, stop blob buffering because V8/Chrome will crash with "Memory Limit"
      const contentLength = response.headers.get("content-length");
      if (contentLength && parseInt(contentLength) > 1.5 * 1024 * 1024 * 1024) {
          throw new Error("❌ File is too large (> 1.5GB) to buffer in RAM! Chrome native download must be fixed.");
      }
      
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = displayName;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();

      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
      }, 1000);

      console.log(`[CradleScanner] ✅ Blob download: ${displayName} (${(blob.size / 1024 / 1024).toFixed(1)} MB)`);

      // Ask Desktop App to move file into cradleId subfolder
      if (cradleId && desktopConnection) {
        setTimeout(() => {
          desktopConnection.sendMessage({
            action: "MOVE_DOWNLOADED_FILE",
            filename: displayName,
            cradleId: cradleId,
            timestamp: Date.now()
          });
          console.log(`[CradleScanner] 📦 Requested move: ${displayName} → ${cradleId}/`);
        }, 2000); // Wait 2s for file to finish writing
      }

      return true;
    } catch (error) {
      console.error(`[CradleScanner] ❌ Download failed for ${displayName}:`, error.message);
      return false;
    }
  }

  // ✅ ACCEPTANCE FILE DOWNLOAD
  async handleAcceptanceFile(fileData, cradleId, preferredFilename = null) {
    console.log("[CradleScanner] 📥 Downloading acceptance file...");
    let filename = preferredFilename || this.extractFilenameFromUrl(fileData.url);
    filename = filename.replace(/[\\/:*?"<>|\r\n]+/g, "_").trim();
    const downloadPath = `${cradleId}/${filename}`;

    const success = await this.downloadViaFetch(fileData.url, downloadPath);
    if (success) {
      this.showNotification(`📥 Acceptance downloaded: ${filename}`, "success");
    } else {
      this.showNotification(`❌ Acceptance download failed: ${filename}`, "error");
    }
  }

  // Helper function to add _emis suffix if needed
  addEmissionSuffix(emissionName, acceptanceName) {
    if (!acceptanceName) return emissionName;
    const emissionFileName = emissionName.split("/").pop();
    const acceptanceFileName = acceptanceName.split("/").pop();
    if (emissionFileName === acceptanceFileName) {
      return emissionName.replace(/(\.[^.]+)$/, "_emis$1");
    }
    return emissionName;
  }

  // ✅ EMISSION FILE DOWNLOAD
  async handleEmissionFile(fileData, cradleId, acceptanceFileName = null) {
    console.log("[CradleScanner] 📡 Handling emission file...");
    console.log("Emission type:", fileData.type);

    if (fileData.type === "attachment") {
      // 📎 EMISSION ATTACHMENT - download via fetch
      let finalFilename = fileData.name || this.extractFilenameFromUrl(fileData.url);

      // Always add _emis suffix to emission files — reliable discriminator for Desktop App
      const dotIndex = finalFilename.lastIndexOf(".");
      if (dotIndex !== -1) {
        finalFilename = finalFilename.substring(0, dotIndex) + "_emis" + finalFilename.substring(dotIndex);
      } else {
        finalFilename = finalFilename + "_emis";
      }
      finalFilename = finalFilename.replace(/[\\/:*?"<>|\r\n]+/g, "_").trim();
      console.log(`[CradleScanner] 🏷️ Emission suffix added: ${finalFilename}`);


      const downloadPath = `${cradleId}/${finalFilename}`;
      const success = await this.downloadViaFetch(fileData.url, downloadPath);
      if (success) {
        this.showNotification(`📡 Emission downloaded: ${finalFilename}`, "success");
      } else {
        this.showNotification(`❌ Emission download failed`, "error");
      }

    } else if (fileData.type === "network_path") {
      // 🌐 NETWORK PATH - Desktop App handles this
      console.log("[CradleScanner] 🌐 Network path detected:", fileData.path);
      this.showNotification(
        `📡 Emission file (network): ${fileData.path.split("/").pop()}`,
        "info"
      );
      console.log("[CradleScanner] 📤 Network emission will be handled by Desktop App");

    } else {
      console.log("[CradleScanner] ⚠️ Unknown emission file type:", fileData.type);
      this.showNotification(`⚠️ Unknown emission type: ${fileData.type}`, "warning");
    }
  }

  async applyQAFilterOnly() {
    if (this.isScanning) {
      console.log("[CradleScanner] Already running...");
      return;
    }

    this.isScanning = true;

    try {
      console.log("[CradleScanner] === APPLYING QA FILTER ===");

      console.log("[CradleScanner] === STEP 1: Applying QA filter ===");
      await this.applyQAFilter();

      console.log("[CradleScanner] === STEP 2: Waiting for filter ===");
      await this.waitForFilter();

      this.status = "Filter applied successfully";
      this.showNotification("QA FINAL PROOFREADING filter applied!", "success");
    } catch (error) {
      console.error("[CradleScanner] ERROR:", error.message);
      this.status = `Error: ${error.message}`;
      this.showNotification(`Error: ${error.message}`, "error");
    } finally {
      this.isScanning = false;
    }
  }

  async applyQAFilter() {
    this.status = "Looking for Saved States button...";

    const savedStatesButton = this.findSavedStatesButton();

    if (!savedStatesButton) {
      throw new Error("Saved States button not found");
    }

    console.log("[CradleScanner] 🎯 Found Saved States button, clicking...");
    this.status = "Clicking Saved States...";

    savedStatesButton.click();

    await this.wait(2000);

    const qaOption = this.findQAOption();

    if (!qaOption) {
      throw new Error("QA FINAL PROOFREADING option not found");
    }

    console.log(
      "[CradleScanner] 🎯 Found QA FINAL PROOFREADING option, clicking..."
    );
    this.status = "Selecting QA FINAL PROOFREADING...";

    qaOption.click();

    console.log("[CradleScanner] ✅ QA filter selected");
  }

  findSavedStatesButton() {
    console.log("[CradleScanner] Looking for Saved States button...");

    const buttons = document.querySelectorAll("button");
    console.log("[CradleScanner] Found", buttons.length, "buttons on page");

    for (const button of buttons) {
      const text = button.textContent.trim();

      if (text.includes("Saved States")) {
        console.log("[CradleScanner] ✅ Found Saved States button:", text);
        return button;
      }
    }

    console.log("[CradleScanner] ❌ Saved States button not found");
    return null;
  }

  // ✅ New helper: Extract clean filename from URL (handles query params)
  extractFilenameFromUrl(url) {
    try {
      // Handle URLs with query parameters
      const urlObj = new URL(url);
      const pathname = urlObj.pathname;
      const filename = pathname.split("/").pop();
      return decodeURIComponent(filename);
    } catch (e) {
      // Fallback for non-standard URLs
      console.warn("Invalid URL for filename extraction:", url);
      try {
        return url.split("/").pop().split("?")[0];
      } catch (e2) {
        return "unknown_file.mp4";
      }
    }
  }

  wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  findQAOption() {
    console.log("[CradleScanner] Looking for QA FINAL PROOFREADING option...");

    const allElements = document.querySelectorAll("*");
    console.log(
      "[CradleScanner] Checking",
      allElements.length,
      "elements for QA option"
    );

    let foundElements = [];

    for (const element of allElements) {
      const text = element.textContent.trim();
      const isVisible = element.offsetParent !== null;

      if (text === "QA FINAL PROOFREADING" && isVisible) {
        foundElements.push(element);
        console.log(
          "[CradleScanner] ✅ Found QA FINAL PROOFREADING option:",
          element.tagName,
          element.className
        );
      }
    }

    if (foundElements.length > 0) {
      console.log("[CradleScanner] Using first QA option");
      return foundElements[0];
    }

    console.log("[CradleScanner] ❌ QA FINAL PROOFREADING option not found");
    return null;
  }

  async waitForFilter() {
    console.log("[CradleScanner] ⏳ Waiting 5 seconds for filter to apply...");
    this.status = "Waiting for filter to apply...";

    await this.wait(5000);

    console.log("[CradleScanner] ✅ Filter wait completed");
  }

  async wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // ✅ New helper: Extract clean filename from URL (handles query params)
  extractFilenameFromUrl(url) {
    try {
      // Handle URLs with query parameters
      const urlObj = new URL(url);
      const pathname = urlObj.pathname;
      const filename = pathname.split("/").pop();
      return decodeURIComponent(filename);
    } catch (e) {
      // Fallback for non-standard URLs
      console.warn("Invalid URL for filename extraction:", url);
      try {
        return url.split("/").pop().split("?")[0];
      } catch (e2) {
        return "unknown_file.mp4";
      }
    }
  }

  // ✅ Extract Template ID and Job Number from asset metadata sidebar
  extractAssetMetadata() {
    const result = { templateId: null, jobNumber: null, langCode: null, clientName: null };
    try {
      const allElements = document.querySelectorAll('td, th, dt, dd, li, span, div');
      for (const el of allElements) {
        const text = el.textContent.trim();

        // Template ID
        if (text === 'Template ID') {
          const next = el.nextElementSibling;
          if (next) { result.templateId = next.textContent.trim(); continue; }
          const parentRow = el.closest('tr');
          if (parentRow) {
            const tds = parentRow.querySelectorAll('td');
            if (tds.length >= 2) result.templateId = tds[tds.length - 1].textContent.trim();
          }
        }

        // Job number
        if (text === 'Job number') {
          const next = el.nextElementSibling;
          if (next) { result.jobNumber = next.textContent.trim(); continue; }
          const parentRow = el.closest('tr');
          if (parentRow) {
            const tds = parentRow.querySelectorAll('td');
            if (tds.length >= 2) result.jobNumber = tds[tds.length - 1].textContent.trim();
          }
        }
        
        // Client / Brand
        if (text === 'Client' || text === 'Brand' || text === 'Organisation' || text === 'Client Name') {
          const next = el.nextElementSibling;
          if (next) { result.clientName = next.textContent.trim(); continue; }
          const parentRow = el.closest('tr');
          if (parentRow) {
            const tds = parentRow.querySelectorAll('td');
            if (tds.length >= 2) result.clientName = tds[tds.length - 1].textContent.trim();
          }
        }

        // Lang — e.g. "Italian (CH) ()" → "IT"
        if (text === 'Lang') {
          const getVal = (el) => {
            const next = el.nextElementSibling;
            if (next) return next.textContent.trim();
            const parentRow = el.closest('tr');
            if (parentRow) {
              const tds = parentRow.querySelectorAll('td');
              if (tds.length >= 2) return tds[tds.length - 1].textContent.trim();
            }
            return null;
          };
          const langRaw = getVal(el);
          if (langRaw) {
            // Map language name → 2-letter ISO code
            const LANG_MAP = {
              'italian':  'IT', 'french':  'FR', 'german':  'DE',
              'english':  'EN', 'spanish': 'ES', 'polish':  'PL',
              'dutch':    'NL', 'portuguese': 'PT', 'russian': 'RU',
              'czech':    'CZ', 'hungarian': 'HU', 'romanian': 'RO',
              'swedish':  'SV', 'danish':  'DA', 'norwegian': 'NO',
              'finnish':  'FI', 'turkish': 'TR', 'greek':    'EL',
            };
            const langLower = langRaw.toLowerCase().split(/[\s(]/)[0]; // take first word
            result.langCode = LANG_MAP[langLower] || null;
            console.log(`[CradleScanner] 🌍 Lang field: '${langRaw}' → langCode: '${result.langCode}'`);
          }
        }
      }
    } catch (e) {
      console.warn('[CradleScanner] extractAssetMetadata error:', e);
    }
    console.log(`[CradleScanner] 📋 Asset metadata — TemplateID: ${result.templateId}, JobNumber: ${result.jobNumber}, LangCode: ${result.langCode}`);
    return result;
  }

  async startVideoCompare(data = {}) {
    // Always use API mode — legacy Playwright mode is deprecated
    const useApi = true;
    const actionType = "VIDEO_COMPARE_API_REQUEST";

    console.log(`[CradleScanner] 🎬 Requesting Video Compare automation (API Mode: ${useApi})...`);

    const cradleId = this.currentCradleId;
    if (!cradleId) {
      this.showNotification("❌ No Cradle ID available", "error");
      console.log("[CradleScanner] ❌ No Cradle ID found for Video Compare");
      return;
    }

    console.log(
      `[CradleScanner] 🎬 Starting Video Compare for CradleID: ${cradleId} via ${actionType}`
    );
    this.showNotification(`🎬 Starting Video Compare (API)...`, "info");
    
    // Set flag so VIDEO_COMPARE_RESULTS handler knows to redirect to results page
    this.isAutoComparing = true;

    // Extract metadata for file discovery
    const extractedMeta = this.extractAssetMetadata();
    const templateId = extractedMeta.templateId;
    const jobNumber = extractedMeta.jobNumber;
    const langCode = extractedMeta.langCode;
    
    // Prefer locally saved client from MyTeam, but fallback to metadata extraction
    let clientName = localStorage.getItem("cradle-current-client");
    if (!clientName && extractedMeta.clientName) {
        clientName = extractedMeta.clientName;
        console.log(`[CradleScanner] 🏢 Client extracted from asset metadata fallback: ${clientName}`);
    } else if (clientName) {
        console.log(`[CradleScanner] 🏢 Client retrieved from localStorage: ${clientName}`);
    } else {
        console.log(`[CradleScanner] ⚠️ Client name not found in localStorage or metadata`);
    }

    // Send request to Desktop App
    const sent = desktopConnection.sendMessage({
      action: actionType,
      cradleId: cradleId,
      templateId: templateId,
      jobNumber: jobNumber,
      langCode: langCode,
      clientName: clientName,
      timestamp: Date.now(),
    });

    if (sent) {
      console.log(
        `[CradleScanner] ✅ ${actionType} sent to Desktop App`
      );
      this.showNotification(
        `📤 Request sent to Desktop App`,
        "info"
      );
    } else {
    console.log("[CradleScanner] ❌ Desktop App not connected");
      this.showNotification("❌ Desktop App not connected", "error");
    }
  }
}

// Inicjalizacja
if (typeof window.cradleScanner === "undefined") {
  window.cradleScanner = new CradleScanner();
}

// === GLOBAL EXPOSURE FOR CONSOLE TESTING ===
window.desktopConnection = desktopConnection;
window.cradleScanner = window.cradleScanner;
console.log("[CradleScanner] ✅ Objects exposed to window for console testing");
console.log(
  '[CradleScanner] Test with: window.desktopConnection.sendMessage({action: "test"})'
);

// === CUSTOM EVENT FOR CONSOLE TESTING ===
document.addEventListener("test-desktop-connection", () => {
  console.log("[CradleScanner] 🧪 Testing desktop connection...");
  if (
    desktopConnection &&
    typeof desktopConnection.sendMessage === "function"
  ) {
    const result = desktopConnection.sendMessage({
      action: "CONSOLE_TEST",
      message: "Hello from console via custom event",
      timestamp: Date.now(),
    });
    console.log("[CradleScanner] ✅ Test message sent, result:", result);
  } else {
    console.error("[CradleScanner] ❌ desktopConnection not available");
  }
});

console.log(
  '[CradleScanner] 🧪 Test available via: document.dispatchEvent(new Event("test-desktop-connection"))'
);


