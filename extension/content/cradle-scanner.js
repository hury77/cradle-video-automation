console.log("Cradle Scanner content script loaded");

class CradleScanner {
  constructor() {
    this.isScanning = false;
    this.status = "Ready";
    this.currentCradleId = null;

    document.addEventListener("extension-command", (event) => {
      console.log("[CradleScanner] Command received:", event.detail.action);
      this.handleCommand(event.detail);
    });

    this.checkAutoApplyFilter();
    this.checkAutoFindAsset();
    this.extractCradleId();

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
    } else {
      console.log(
        "[CradleScanner] ⚠️ Could not extract Cradle ID from URL:",
        window.location.href
      );
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

  handleCommand(eventDetail) {
    console.log("[CradleScanner] Event detail received:", eventDetail);
    const action = eventDetail.action;
    console.log("[CradleScanner] Action extracted:", action);

    switch (action) {
      case "START_AUTOMATION":
        this.startAutomation();
        break;
      case "STOP_AUTOMATION":
        this.stopAutomation();
        break;
      case "FIND_ASSET":
        this.findPendingAsset();
        break;
      case "TAKE_ASSET":
        this.takeAsset();
        break;
      case "DOWNLOAD_FILES":
        this.downloadFiles();
        break;
      case "GET_STATUS":
        this.sendStatus();
        break;
      default:
        console.warn("[CradleScanner] ⚠️ Unknown action:", action);
    }
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
            console.log(`[CradleScanner] Table ${i} first cell: "${cellText}"`);
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

          console.log(
            `[CradleScanner] ✅ Found earliest pending asset: ${cradleId}`
          );
          console.log(`[CradleScanner] Opening URL: ${assetUrl}`);

          this.status = `Opening asset ${cradleId}`;
          this.showNotification(
            `✅ Opening pending asset ${cradleId}...`,
            "success"
          );

          window.open(assetUrl, "_blank");

          this.status = "Ready";
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

      alert(
        "❌ No Pending Assets Found\n\nAll assets are either:\n• Already Processing (someone is working on them)\n• Completed\n• No assets match QA final proofreading filter\n\nPlease check back later or verify the filter settings."
      );
    } catch (error) {
      console.error("[CradleScanner] Error finding pending asset:", error);
      this.status = `Error: ${error.message}`;
      this.showNotification(`❌ Error: ${error.message}`, "error");

      alert(
        `❌ Error Finding Assets\n\n${error.message}\n\nPlease check:\n• Are you on the correct page?\n• Is the QA filter applied?\n• Are there any assets in the table?`
      );
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

        return;
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

          return;
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

        return;
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
    } catch (error) {
      console.error("[CradleScanner] Error taking asset:", error);
      this.status = `Error: ${error.message}`;
      this.showNotification(`❌ Error: ${error.message}`, "error");
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
    try {
      this.showNotification("📁 Starting file download process...", "info");
      console.log("[CradleScanner] 📁 Starting download files process...");

      if (!this.currentCradleId) {
        this.extractCradleId();
        if (!this.currentCradleId) {
          throw new Error(
            "Cradle ID not found. Please ensure you are on asset details page."
          );
        }
      }

      console.log("[CradleScanner] 🔍 Scanning Asset comments table...");

      const commentsTable = await this.findAssetCommentsTable();
      if (!commentsTable) {
        throw new Error("Asset comments table not found");
      }

      const fileInfo = await this.scanForFiles(commentsTable);

      if (!fileInfo.emissionFile && !fileInfo.acceptanceFile) {
        throw new Error("No files found for download");
      }

      console.log("[CradleScanner] 📁 Files found:", fileInfo);

      await this.createDownloadFolder();

      if (fileInfo.acceptanceFile) {
        await this.downloadAcceptanceFile(fileInfo.acceptanceFile);
      }

      if (fileInfo.emissionFile) {
        await this.handleEmissionFile(fileInfo.emissionFile);
      }

      this.showNotification(
        "✅ File download completed successfully!",
        "success"
      );
    } catch (error) {
      console.error("[CradleScanner] ❌ Download files error:", error);
      this.showNotification(`❌ Download failed: ${error.message}`, "error");
    }
  }

  async findAssetCommentsTable() {
    console.log("[CradleScanner] 🔍 Looking for Asset comments table...");

    for (let i = 0; i < 10; i++) {
      console.log(`[CradleScanner] ⏳ Table search attempt ${i + 1}/10`);

      const tables = document.querySelectorAll("table");
      console.log(`[CradleScanner] Found ${tables.length} tables on page`);

      for (let j = 0; j < tables.length; j++) {
        const table = tables[j];
        const headers = table.querySelectorAll("th");
        console.log(
          `[CradleScanner] Table ${j} headers:`,
          Array.from(headers).map((h) => h.textContent.trim())
        );

        for (const header of headers) {
          const headerText = header.textContent.trim();
          if (
            headerText.includes("Asset comments") ||
            headerText.includes("Comment") ||
            headerText.includes("Attachment")
          ) {
            console.log(
              "[CradleScanner] ✅ Found Asset comments table via header:",
              headerText
            );
            return table;
          }
        }
      }

      for (let j = 0; j < tables.length; j++) {
        const table = tables[j];
        const rows = table.querySelectorAll("tr");

        for (const row of rows) {
          const cells = row.querySelectorAll("td");
          for (const cell of cells) {
            const cellText = cell.textContent.toLowerCase();
            if (
              cellText.includes("qa proofreading") ||
              cellText.includes("final file preparation") ||
              cellText.includes("broadcast preparation")
            ) {
              console.log(
                "[CradleScanner] ✅ Found Asset comments table via content"
              );
              return table;
            }
          }
        }
      }

      console.log(`[CradleScanner] ⏳ Waiting for table... (${i + 1}/10)`);
      await this.wait(1000);
    }

    console.log(
      "[CradleScanner] ❌ Asset comments table not found after 10 attempts"
    );
    return null;
  }

  async scanForFiles(table) {
    console.log("[CradleScanner] 🔍 Scanning table rows for files...");

    const fileInfo = {
      emissionFile: null,
      acceptanceFile: null,
    };

    const rows = table.querySelectorAll("tbody tr");
    if (rows.length === 0) {
      const allRows = table.querySelectorAll("tr");
      console.log(
        `[CradleScanner] No tbody rows, trying all rows: ${allRows.length}`
      );

      allRows.forEach((row, index) => {
        this.scanRowForFiles(row, index, fileInfo);
      });
    } else {
      console.log(`[CradleScanner] 📊 Found ${rows.length} tbody rows to scan`);

      rows.forEach((row, index) => {
        this.scanRowForFiles(row, index, fileInfo);
      });
    }

    console.log("[CradleScanner] 📁 File scan results:", fileInfo);
    return fileInfo;
  }

  scanRowForFiles(row, index, fileInfo) {
    const cells = row.querySelectorAll("td");
    if (cells.length < 2) return;

    console.log(`[CradleScanner] 📝 Row ${index + 1}: ${cells.length} cells`);

    let commentText = "";
    let attachmentUrl = null;

    for (let i = 0; i < cells.length; i++) {
      const cellText = cells[i].textContent.toLowerCase();

      if (i === 6) {
        const link = cells[i].querySelector("a[href]");
        if (
          link &&
          !link.href.includes("Omit in Shop") &&
          link.textContent.trim() !== "Omit in Shop"
        ) {
          attachmentUrl = link.href;
          console.log(`[CradleScanner] Found attachment:`, attachmentUrl);
        }
      }

      if (i === 0) {
        commentText = cellText;
      }
    }

    if (!commentText) return;

    if (
      commentText.includes("final file preparation") ||
      commentText.includes("broadcast preparation")
    ) {
      console.log("[CradleScanner] 🎬 Found emission file row");

      let path = null;
      const commentCell = cells[2];
      if (commentCell) {
        const pathMatch = commentCell.textContent.match(/\/Volumes\/[^\s]+/);
        if (pathMatch) {
          path = pathMatch[0];
        }
      }

      fileInfo.emissionFile = {
        type: "emission",
        path: path,
        attachment: attachmentUrl,
        row: row,
      };
    }

    if (
      (commentText.includes("qa proofreading") ||
        commentText.includes("qc_final") ||
        commentText.includes("qc final")) &&
      attachmentUrl
    ) {
      console.log(
        "[CradleScanner] ✅ Found acceptance file row with attachment"
      );

      if (!fileInfo.acceptanceFile) {
        fileInfo.acceptanceFile = {
          type: "acceptance",
          attachment: attachmentUrl,
          row: row,
        };
      }
    }
  }

  async createDownloadFolder() {
    console.log(
      `[CradleScanner] 📂 Preparing download folder: ${this.currentCradleId}`
    );
    this.showNotification(
      `📂 Files will be organized in: Downloads/${this.currentCradleId}/`,
      "info"
    );
    this.showNotification(`🔧 Chrome will create folder automatically`, "info");
  }

  async downloadAcceptanceFile(fileInfo) {
    if (!fileInfo.attachment) {
      console.warn(
        "[CradleScanner] ⚠️ No attachment found for acceptance file"
      );
      this.showNotification(
        "⚠️ No acceptance file attachment found",
        "warning"
      );
      return;
    }

    console.log(
      "[CradleScanner] ⬇️ Downloading acceptance file:",
      fileInfo.attachment
    );
    this.showNotification("⬇️ Downloading acceptance file...", "info");

    try {
      // ✅ ZACHOWAJ ORYGINALNĄ NAZWĘ PLIKU
      const originalFilename = decodeURIComponent(
        fileInfo.attachment.split("/").pop()
      );
      console.log("[CradleScanner] Original filename:", originalFilename);

      // Utwórz link z folderem w nazwie (Chrome automatycznie utworzy folder)
      const link = document.createElement("a");
      link.href = fileInfo.attachment;
      link.download = `${this.currentCradleId}/${originalFilename}`; // ✅ Folder + oryginalna nazwa
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      console.log(
        "[CradleScanner] ✅ Acceptance file download triggered:",
        originalFilename
      );
      this.showNotification(`✅ Downloading: ${originalFilename}`, "success");
      this.showNotification(
        `📂 Saved to: Downloads/${this.currentCradleId}/`,
        "info"
      );
    } catch (error) {
      console.error("[CradleScanner] ❌ Acceptance download error:", error);
      this.showNotification(`❌ Download failed: ${error.message}`, "error");
    }
  }

  async handleEmissionFile(fileInfo) {
    if (fileInfo.attachment) {
      console.log(
        "[CradleScanner] ⬇️ Downloading emission file attachment:",
        fileInfo.attachment
      );
      this.showNotification("⬇️ Downloading emission file...", "info");

      try {
        // ✅ ZACHOWAJ ORYGINALNĄ NAZWĘ PLIKU
        const originalFilename = decodeURIComponent(
          fileInfo.attachment.split("/").pop()
        );
        console.log("[CradleScanner] Original filename:", originalFilename);

        const link = document.createElement("a");
        link.href = fileInfo.attachment;
        link.download = `${this.currentCradleId}/${originalFilename}`; // ✅ Folder + oryginalna nazwa
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        console.log(
          "[CradleScanner] ✅ Emission file download triggered:",
          originalFilename
        );
        this.showNotification(`✅ Downloading: ${originalFilename}`, "success");
        this.showNotification(
          `📂 Saved to: Downloads/${this.currentCradleId}/`,
          "info"
        );
      } catch (error) {
        console.error("[CradleScanner] ❌ Emission download error:", error);
        this.showNotification(`❌ Download failed: ${error.message}`, "error");
      }
    } else if (fileInfo.path) {
      console.log(
        "[CradleScanner] 📁 Found emission file network path:",
        fileInfo.path
      );

      // ✅ ULEPSZONA OBSŁUGA DYSKU SIECIOWEGO
      const fullPath = `${fileInfo.path}/broadcast`; // Często pliki są w podfolderze

      // Spróbuj skopiować do schowka z różnymi metodami
      try {
        // Metoda 1: Nowoczesny API
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(fullPath);
          this.showNotification(`📋 Path copied to clipboard!`, "success");
          console.log(
            "[CradleScanner] ✅ Path copied to clipboard (modern API):",
            fullPath
          );
        } else {
          throw new Error("Clipboard API not available");
        }
      } catch (error) {
        console.log(
          "[CradleScanner] Modern clipboard failed, trying fallback..."
        );

        // Metoda 2: Fallback - stary sposób
        try {
          const textArea = document.createElement("textarea");
          textArea.value = fullPath;
          textArea.style.position = "fixed";
          textArea.style.opacity = "0";
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();

          const successful = document.execCommand("copy");
          document.body.removeChild(textArea);

          if (successful) {
            this.showNotification(`📋 Path copied to clipboard!`, "success");
            console.log(
              "[CradleScanner] ✅ Path copied to clipboard (fallback):",
              fullPath
            );
          } else {
            throw new Error("execCommand failed");
          }
        } catch (fallbackError) {
          console.log(
            "[CradleScanner] ⚠️ Could not copy to clipboard:",
            fallbackError
          );

          // Metoda 3: Pokaż instrukcje
          this.showNotification(`📁 Network Path: ${fullPath}`, "info");
          this.showNotification(
            `🔍 Look for file: ${this.currentCradleId}*.*`,
            "info"
          );
          this.showNotification(
            `📋 Copy path manually from console`,
            "warning"
          );

          // Dodatkowy alert z instrukcjami
          setTimeout(() => {
            alert(
              `🎬 EMISSION FILE LOCATION\n\nPath: ${fullPath}\n\nInstructions:\n1. Open Finder/File Explorer\n2. Navigate to above path\n3. Look for file starting with: ${this.currentCradleId}\n4. Copy file to Downloads/${this.currentCradleId}/ folder\n\nPath has been logged to console for easy copying.`
            );
          }, 1000);
        }
      }

      // POKAŻ SZCZEGÓŁOWE INSTRUKCJE
      this.showNotification(`🎯 Instructions: Open ${fullPath}`, "info");
      this.showNotification(
        `📄 Find file: ${this.currentCradleId}_*.mp4`,
        "info"
      );
      this.showNotification(
        `💾 Copy to: Downloads/${this.currentCradleId}/`,
        "info"
      );
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

  stopAutomation() {
    this.isScanning = false;
    this.status = "Stopped";
    console.log("[CradleScanner] Automation stopped");
  }
}

// Inicjalizacja
if (typeof window.cradleScanner === "undefined") {
  window.cradleScanner = new CradleScanner();
}
