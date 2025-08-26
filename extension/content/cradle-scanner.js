console.log("Cradle Scanner content script loaded");

class CradleScanner {
  constructor() {
    this.isScanning = false;
    this.status = "Ready";
    this.currentCradleId = null;

    document.addEventListener("extension-command", async (event) => {
      await this.handleCommand(event);
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
      default:
        console.log("[CradleScanner] Unknown command:", action);
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
    console.log("=== ROZPOCZYNAM POBIERANIE PLIKÓW ===");

    const cradleId = this.extractCradleId();
    console.log("Cradle ID:", cradleId);

    if (!cradleId) {
      this.showNotification("Nie można pobrać Cradle ID z URL", "error");
      return;
    }

    // Find and scan the asset comments table - TUTAJ JEST KLUCZOWA ZMIANA
    const table = await this.findAssetCommentsTable();

    // ✅ DODAJ DEBUGOWANIE
    console.log("[CradleScanner] 🔍 DEBUG: Table received in downloadFiles:");
    console.log("[CradleScanner] Table type:", typeof table);
    console.log("[CradleScanner] Table constructor:", table?.constructor?.name);
    console.log("[CradleScanner] Table tagName:", table?.tagName);
    console.log("[CradleScanner] Table object:", table);

    const fileInfo = this.scanForFiles(table);

    console.log("=== WYNIKI SKANOWANIA PLIKÓW ===");
    console.log("Pełne fileInfo:", fileInfo);

    // Download acceptance file if found
    if (fileInfo.acceptanceFile) {
      console.log("✓ ZNALEZIONO PLIK AKCEPTACJI:");
      console.log("  - Nazwa:", fileInfo.acceptanceFile.filename);
      console.log("  - URL:", fileInfo.acceptanceFile.url);
      console.log("  - Rząd:", fileInfo.acceptanceFile.row);

      await this.handleAcceptanceFile(fileInfo.acceptanceFile, cradleId);
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

      await this.handleEmissionFile(fileInfo.emissionFile, cradleId);
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
  }

  async findAssetCommentsTable() {
    console.log("[CradleScanner] 🔍 Looking for Asset comments table...");

    const maxAttempts = 10;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      console.log(
        `[CradleScanner] ⏳ Table search attempt ${attempt}/${maxAttempts}`
      );

      const tables = document.querySelectorAll("table");
      console.log(`[CradleScanner] Found ${tables.length} tables on page`);

      for (let table of tables) {
        // Method 1: Check for "Asset comments" or "Comment" in headers
        const headers = table.querySelectorAll("th");
        for (let header of headers) {
          const headerText = header.textContent.trim().toLowerCase();
          if (
            headerText.includes("asset comments") ||
            headerText.includes("comment") ||
            headerText.includes("attachment")
          ) {
            console.log(
              `[CradleScanner] ✅ Found Asset comments table via header: ${header.textContent.trim()}`
            );
            console.log("[CradleScanner] Returning table:", table);
            return table;
          }
        }

        // Method 2: Check for key phrases in any cell
        const cells = table.querySelectorAll("td, th");
        for (let cell of cells) {
          const cellText = cell.textContent.trim().toLowerCase();
          if (
            cellText.includes("qa proofreading") ||
            cellText.includes("final file preparation") ||
            cellText.includes("broadcast preparation") ||
            cellText.includes("file preparation")
          ) {
            console.log(
              `[CradleScanner] ✅ Found Asset comments table via content: ${cellText}`
            );
            console.log("[CradleScanner] Returning table:", table);
            return table;
          }
        }
      }

      if (attempt < maxAttempts) {
        console.log(
          `[CradleScanner] ⏳ Table not found, waiting 1 second... (${attempt}/${maxAttempts})`
        );
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }

    console.log(
      "[CradleScanner] ❌ Asset comments table not found after all attempts"
    );
    return null;
  }

  scanForFiles(table) {
    console.log("[CradleScanner] 🔍 Scanning table rows for files...");

    // === KRYTYCZNA WALIDACJA ===
    console.log("[CradleScanner] 🔍 Validating table object...");
    console.log("[CradleScanner] Table type:", typeof table);
    console.log("[CradleScanner] Table constructor:", table?.constructor?.name);
    console.log("[CradleScanner] Table tagName:", table?.tagName);
    console.log(
      "[CradleScanner] Has querySelectorAll:",
      typeof table?.querySelectorAll
    );

    if (!table) {
      console.error("[CradleScanner] ❌ Table is null or undefined");
      return { acceptanceFile: null, emissionFile: null };
    }

    if (
      !table.querySelectorAll ||
      typeof table.querySelectorAll !== "function"
    ) {
      console.error(
        "[CradleScanner] ❌ Table does not have querySelectorAll method"
      );
      console.error("[CradleScanner] Table object:", table);
      return { acceptanceFile: null, emissionFile: null };
    }

    if (table.tagName !== "TABLE") {
      console.error(
        "[CradleScanner] ❌ Element is not a TABLE:",
        table.tagName
      );
      return { acceptanceFile: null, emissionFile: null };
    }

    console.log("[CradleScanner] ✅ Table validation passed");

    // === SKANOWANIE WIERSZY ===
    const fileInfo = {
      emissionFile: null,
      acceptanceFile: null,
    };

    try {
      let rows = table.querySelectorAll("tbody tr");
      if (rows.length === 0) {
        console.log("[CradleScanner] No tbody rows, trying all tr elements...");
        rows = table.querySelectorAll("tr");
      }

      console.log(`[CradleScanner] Found ${rows.length} rows to scan`);

      if (rows.length === 0) {
        console.log("[CradleScanner] ❌ No rows found in table");
        return fileInfo;
      }

      // === SKANOWANIE KAŻDEGO WIERSZA ===
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        console.log(
          `[CradleScanner] --- Scanning row ${i + 1}/${rows.length} ---`
        );

        try {
          // === ANALIZA WIERSZA ===
          const cells = row.querySelectorAll("td");
          if (cells.length === 0) {
            console.log(
              `[CradleScanner] Row ${i + 1}: No cells found, skipping`
            );
            continue;
          }

          const firstCellText = cells[0].textContent.toLowerCase().trim();
          console.log(
            `[CradleScanner] Row ${i + 1}: "${firstCellText.substring(
              0,
              80
            )}..."`
          );

          // === EMISSION FILES - SPRAWDŹ NAJPIERW! ===
          // 1. Szukaj w wierszach: "final file preparation" - sprawdź kolumnę Comment
          if (firstCellText.includes("final file preparation")) {
            console.log(
              `[CradleScanner] Row ${
                i + 1
              }: 📡 Final file preparation - sprawdzam kolumnę Comment`
            );

            cells.forEach((cell, cellIndex) => {
              const cellText = cell.textContent.trim();

              // Sprawdź czy to ścieżka sieciowa w kolumnie Comment
              if (
                (cellText.includes("/Volumes/") || cellText.includes("\\\\")) &&
                !fileInfo.emissionFile
              ) {
                console.log(
                  `[CradleScanner] Row ${
                    i + 1
                  }, Cell ${cellIndex}: 🌐 ŚCIEŻKA SIECIOWA w Comment`
                );
                console.log(`[CradleScanner] Ścieżka: "${cellText}"`);

                fileInfo.emissionFile = {
                  type: "network_path",
                  path: cellText,
                  name: `emission_from_network`,
                  row: i + 1,
                  cell: cellIndex,
                };

                console.log(
                  `[CradleScanner] ✅ EMISSION PATH found in row ${
                    i + 1
                  }, cell ${cellIndex}`
                );
              }

              // Sprawdź też czy nie ma załącznika (jak wcześniej)
              const attachmentLink =
                cell.querySelector('a[href^="/media/cradle/comment/"]') ||
                cell.querySelector("a i.fa-file")?.parentElement;

              if (
                attachmentLink &&
                attachmentLink.href &&
                !fileInfo.emissionFile
              ) {
                const fileName =
                  attachmentLink.href.split("/").pop() ||
                  `emission_${Date.now()}.mp4`;
                const fullUrl = attachmentLink.href.startsWith("http")
                  ? attachmentLink.href
                  : `https://cradle.egplusww.pl${attachmentLink.href}`;

                fileInfo.emissionFile = {
                  type: "attachment",
                  url: fullUrl,
                  name: fileName,
                  row: i + 1,
                  cell: cellIndex,
                };
                console.log(
                  `[CradleScanner] ✅ EMISSION ATTACHMENT found in row ${
                    i + 1
                  }, cell ${cellIndex}: ${fileName}`
                );
              }
            });
          }

          // 2. Szukaj w wierszach: "broadcast file preparation" (alternatywny wzorzec)
          else if (firstCellText.includes("broadcast file preparation")) {
            console.log(
              `[CradleScanner] Row ${
                i + 1
              }: 📡 Broadcast file preparation - potencjalny plik EMISSION`
            );

            cells.forEach((cell, cellIndex) => {
              const cellText = cell.textContent.trim();

              // Sprawdź ścieżkę sieciową
              if (
                (cellText.includes("/Volumes/") || cellText.includes("\\\\")) &&
                !fileInfo.emissionFile
              ) {
                fileInfo.emissionFile = {
                  type: "network_path",
                  path: cellText,
                  name: `emission_from_network`,
                  row: i + 1,
                  cell: cellIndex,
                };

                console.log(
                  `[CradleScanner] ✅ EMISSION PATH (broadcast) found in row ${
                    i + 1
                  }, cell ${cellIndex}`
                );
              }

              // Sprawdź załączniki
              const attachmentLink =
                cell.querySelector('a[href^="/media/cradle/comment/"]') ||
                cell.querySelector("a i.fa-file")?.parentElement;

              if (
                attachmentLink &&
                attachmentLink.href &&
                !fileInfo.emissionFile
              ) {
                const fileName =
                  attachmentLink.href.split("/").pop() ||
                  `emission_${Date.now()}.mp4`;
                const fullUrl = attachmentLink.href.startsWith("http")
                  ? attachmentLink.href
                  : `https://cradle.egplusww.pl${attachmentLink.href}`;

                fileInfo.emissionFile = {
                  type: "attachment",
                  url: fullUrl,
                  name: fileName,
                  row: i + 1,
                  cell: cellIndex,
                };
                console.log(
                  `[CradleScanner] ✅ EMISSION ATTACHMENT (broadcast) found in row ${
                    i + 1
                  }, cell ${cellIndex}: ${fileName}`
                );
              }
            });
          }

          // === ACCEPTANCE FILES - SPRAWDŹ PO EMISSION ===
          // Szukaj w wierszach: "file preparation" (ale NIE "final file preparation" ani "broadcast file preparation")
          else if (
            firstCellText.includes("file preparation") &&
            !firstCellText.includes("final") &&
            !firstCellText.includes("broadcast")
          ) {
            console.log(
              `[CradleScanner] Row ${
                i + 1
              }: 📎 File preparation (bez final/broadcast) - potencjalny plik ACCEPTANCE`
            );

            cells.forEach((cell, cellIndex) => {
              // POPRAWIONY SELEKTOR - szuka linków z /media/cradle/comment/
              const attachmentLink =
                cell.querySelector('a[href^="/media/cradle/comment/"]') ||
                cell.querySelector("a i.fa-file")?.parentElement;

              if (
                attachmentLink &&
                attachmentLink.href &&
                !fileInfo.acceptanceFile
              ) {
                const fileName =
                  attachmentLink.href.split("/").pop() ||
                  `acceptance_${Date.now()}.mp4`;
                const fullUrl = attachmentLink.href.startsWith("http")
                  ? attachmentLink.href
                  : `https://cradle.egplusww.pl${attachmentLink.href}`;

                fileInfo.acceptanceFile = {
                  type: "attachment",
                  url: fullUrl,
                  name: fileName,
                  row: i + 1,
                  cell: cellIndex,
                };
                console.log(
                  `[CradleScanner] ✅ ACCEPTANCE FILE found in row ${
                    i + 1
                  }, cell ${cellIndex}: ${fileName}`
                );
                console.log(`[CradleScanner]    URL: ${fullUrl}`);
              }
            });
          }

          // === QA PROOFREADING FALLBACK ===
          else if (
            firstCellText.includes("qa proofreading") &&
            !fileInfo.acceptanceFile
          ) {
            console.log(
              `[CradleScanner] Row ${
                i + 1
              }: 📎 QA proofreading - sprawdzam załączniki (fallback)`
            );

            cells.forEach((cell, cellIndex) => {
              const attachmentLink =
                cell.querySelector('a[href^="/media/cradle/comment/"]') ||
                cell.querySelector("a i.fa-file")?.parentElement;

              if (
                attachmentLink &&
                attachmentLink.href &&
                !fileInfo.acceptanceFile
              ) {
                const fileName =
                  attachmentLink.href.split("/").pop() ||
                  `qa_acceptance_${Date.now()}.mp4`;
                const fullUrl = attachmentLink.href.startsWith("http")
                  ? attachmentLink.href
                  : `https://cradle.egplusww.pl${attachmentLink.href}`;

                fileInfo.acceptanceFile = {
                  type: "attachment",
                  url: fullUrl,
                  name: fileName,
                  row: i + 1,
                  cell: cellIndex,
                };
                console.log(
                  `[CradleScanner] ✅ QA ACCEPTANCE FILE found in row ${
                    i + 1
                  }, cell ${cellIndex}: ${fileName}`
                );
              }
            });
          }
        } catch (rowError) {
          console.error(
            `[CradleScanner] Error scanning row ${i + 1}:`,
            rowError
          );
        }
      }

      // === PODSUMOWANIE WYNIKÓW ===
      console.log("[CradleScanner] 📋 === FINAL SCAN RESULTS ===");
      console.log(
        "[CradleScanner] - Acceptance file:",
        fileInfo.acceptanceFile
          ? `FOUND: ${fileInfo.acceptanceFile.name}`
          : "NOT FOUND"
      );
      console.log(
        "[CradleScanner] - Emission file:",
        fileInfo.emissionFile
          ? `FOUND: ${fileInfo.emissionFile.name || fileInfo.emissionFile.path}`
          : "NOT FOUND"
      );
      console.log("[CradleScanner] === END SCAN RESULTS ===");

      return fileInfo;
    } catch (scanError) {
      console.error(
        "[CradleScanner] ❌ Error during table scanning:",
        scanError
      );
      return { acceptanceFile: null, emissionFile: null };
    }
  }

  async copyToClipboard(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        console.log("[CradleScanner] ✅ Copied to clipboard via Clipboard API");
      } else {
        // Fallback method
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        console.log(
          "[CradleScanner] ✅ Copied to clipboard via fallback method"
        );
      }
    } catch (error) {
      console.error("[CradleScanner] ❌ Failed to copy to clipboard:", error);
      throw error;
    }
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
      const originalFilename = decodeURIComponent(
        fileInfo.attachment.split("/").pop()
      );
      console.log("[CradleScanner] Original filename:", originalFilename);

      // ✅ UŻYJ ISTNIEJĄCEGO BACKGROUND SERVICE
      chrome.runtime.sendMessage(
        {
          action: "DOWNLOAD_FILE",
          url: fileInfo.attachment,
          filename: `${this.currentCradleId}/${originalFilename}`,
        },
        (response) => {
          if (response && response.success) {
            console.log("[CradleScanner] ✅ Acceptance file download started");
            this.showNotification(
              `✅ Downloading: ${originalFilename}`,
              "success"
            );
            this.showNotification(
              `📂 Saved to: Downloads/${this.currentCradleId}/`,
              "info"
            );
          } else {
            console.error(
              "[CradleScanner] ❌ Download failed:",
              response?.error
            );
            this.showNotification(
              `❌ Download failed: ${response?.error}`,
              "error"
            );
          }
        }
      );
    } catch (error) {
      console.error("[CradleScanner] ❌ Acceptance download error:", error);
      this.showNotification(`❌ Download failed: ${error.message}`, "error");
    }
  }

  async handleAcceptanceFile(acceptanceFile, cradleId) {
    console.log("[CradleScanner] 📥 Handling acceptance file...");
    console.log("File data:", acceptanceFile);

    if (acceptanceFile.url) {
      // Wyciągnij oryginalną nazwę z URL
      const filename = acceptanceFile.url
        ? decodeURIComponent(acceptanceFile.url.split("/").pop())
        : acceptanceFile.name || "acceptance_file";
      const downloadPath = `${cradleId}/${filename}`;

      console.log(
        "[CradleScanner] 📤 Sending download request to background..."
      );
      console.log("URL:", acceptanceFile.url);
      console.log("Path:", downloadPath);

      chrome.runtime.sendMessage({
        action: "DOWNLOAD_FILE",
        url: acceptanceFile.url,
        filename: downloadPath,
      });

      this.showNotification(
        `Pobieranie pliku akceptacji: ${filename}`,
        "success"
      );
    } else {
      console.log("[CradleScanner] ❌ No URL found for acceptance file");
      this.showNotification("Brak URL dla pliku akceptacji", "error");
    }
  }

  // ✅ POPRAWIONA METODA - Obsługa pliku emisyjnego
  async handleEmissionFile(emissionFile, cradleId) {
    console.log("[CradleScanner] 📡 Handling emission file...");
    console.log("Emission file data:", emissionFile);

    if (emissionFile.url) {
      // Handle direct attachment
      // Wyciągnij oryginalną nazwę z URL
      const filename = emissionFile.url
        ? decodeURIComponent(emissionFile.url.split("/").pop())
        : emissionFile.name || "emission_file";
      const downloadPath = `${cradleId}/${filename}`;

      console.log(
        "[CradleScanner] 📤 Sending download request to background..."
      );
      console.log("URL:", emissionFile.url);
      console.log("Path:", downloadPath);

      chrome.runtime.sendMessage({
        action: "DOWNLOAD_FILE",
        url: emissionFile.url,
        filename: downloadPath,
      });

      this.showNotification(`Pobieranie pliku emisji: ${filename}`, "success");
    } else if (emissionFile.path) {
      // Handle network path
      console.log(
        "[CradleScanner] 🌐 Handling network path for emission file..."
      );
      console.log("Network path:", emissionFile.path);

      // Try to search for files in the network path
      await this.searchForEmissionFile(emissionFile.path, cradleId);
    } else {
      console.log("[CradleScanner] ❌ No URL or path found for emission file");
      this.showNotification("Brak URL lub ścieżki dla pliku emisji", "error");
    }
  }

  // ✅ NOWA METODA - Znajdź i pobierz plik emisyjny z dysku sieciowego
  async findAndDownloadEmissionFile(networkPath) {
    try {
      this.showNotification(
        "🔍 Searching for emission file on network drive...",
        "info"
      );
      console.log(
        `[CradleScanner] 🔍 Searching for file starting with: ${this.currentCradleId}`
      );

      // Sprawdź czy ścieżka kończy się na /broadcast, jeśli nie - dodaj
      let searchPath = networkPath;
      if (!searchPath.endsWith("/broadcast")) {
        searchPath = `${searchPath}/broadcast`;
      }

      console.log(`[CradleScanner] 🔍 Full search path: ${searchPath}`);

      // Spróbuj znaleźć plik różnymi metodami
      const foundFile = await this.searchForEmissionFile(searchPath);

      if (foundFile) {
        console.log(`[CradleScanner] ✅ Found emission file: ${foundFile}`);
        this.showNotification(`✅ Found: ${foundFile}`, "success");

        // Pobierz znaleziony plik
        await this.downloadNetworkFile(foundFile);
      } else {
        console.log("[CradleScanner] ❌ Emission file not found automatically");

        // Fallback - skopiuj ścieżkę i pokaż instrukcje
        await this.fallbackEmissionFileInstructions(searchPath);
      }
    } catch (error) {
      console.error("[CradleScanner] ❌ Error handling emission file:", error);
      this.showNotification(`❌ Error: ${error.message}`, "error");

      // Fallback
      await this.fallbackEmissionFileInstructions(networkPath);
    }
  }

  // ✅ NOWA METODA - Szukaj pliku emisyjnego w katalogu
  async searchForEmissionFile(searchPath) {
    const possibleExtensions = [".mp4", ".mov", ".avi", ".mkv"];
    const possiblePatterns = [
      `${this.currentCradleId}_`, // CradleID na początku: "875893_filename.mp4"
      `_${this.currentCradleId}_`, // CradleID w środku: "prefix_875893_filename.mp4"
      `_${this.currentCradleId}.`, // CradleID przed rozszerzeniem: "prefix_875893.mp4"
      `${this.currentCradleId}.`, // CradleID bezpośrednio: "875893.mp4"
      `${this.currentCradleId}`, // CradleID bez separatora
    ];

    console.log(`[CradleScanner] 🔍 Trying to access: ${searchPath}`);

    // Spróbuj różne kombinacje nazw plików
    for (const pattern of possiblePatterns) {
      for (const ext of possibleExtensions) {
        const possibleFiles = [
          `${searchPath}/${pattern}${ext}`,
          `${searchPath}/${pattern}*${ext}`, // nie będzie działać bezpośrednio, ale logujemy
        ];

        for (const filePath of possibleFiles) {
          try {
            console.log(`[CradleScanner] 🔍 Checking: ${filePath}`);

            // Spróbuj dostępu przez file:// protocol
            const fileUrl = `file://${filePath}`;
            const response = await fetch(fileUrl, { method: "HEAD" });

            if (response.ok) {
              console.log(`[CradleScanner] ✅ File exists: ${filePath}`);
              return filePath;
            }
          } catch (error) {
            // Plik nie istnieje - kontynuuj szukanie
            console.log(`[CradleScanner] ❌ File not found: ${filePath}`);
          }
        }
      }
    }

    // Spróbuj także bezpośredniego listowania katalogu (jeśli możliwe)
    try {
      console.log(`[CradleScanner] 🔍 Trying directory listing: ${searchPath}`);
      const dirResponse = await fetch(`file://${searchPath}/`);

      if (dirResponse.ok) {
        const dirContent = await dirResponse.text();
        console.log(
          `[CradleScanner] 📁 Directory content preview:`,
          dirContent.substring(0, 500)
        );

        // Szukaj CradleID w zawartości
        const cradleIdRegex = new RegExp(
          `${this.currentCradleId}[^"]*\\.(mp4|mov|avi|mkv)`,
          "gi"
        );
        const matches = dirContent.match(cradleIdRegex);

        if (matches && matches.length > 0) {
          const fileName = matches[0];
          const fullPath = `${searchPath}/${fileName}`;
          console.log(
            `[CradleScanner] ✅ Found file via directory listing: ${fullPath}`
          );
          return fullPath;
        }
      }
    } catch (error) {
      console.log("[CradleScanner] ❌ Directory listing failed:", error);
    }

    return null;
  }

  // ✅ NOWA METODA - Pobierz plik z dysku sieciowego
  async downloadNetworkFile(filePath) {
    try {
      console.log(`[CradleScanner] ⬇️ Downloading network file: ${filePath}`);
      this.showNotification(
        "⬇️ Downloading emission file from network drive...",
        "info"
      );

      const fileName = filePath.split("/").pop();

      // ✅ UŻYJ ISTNIEJĄCEGO BACKGROUND SERVICE
      chrome.runtime.sendMessage(
        {
          action: "DOWNLOAD_FILE",
          url: `file://${filePath}`,
          filename: `${this.currentCradleId}/${fileName}`,
        },
        (response) => {
          if (response && response.success) {
            console.log(
              `[CradleScanner] ✅ Network file download started: ${fileName}`
            );
            this.showNotification(`✅ Downloading: ${fileName}`, "success");
            this.showNotification(
              `📂 Saved to: Downloads/${this.currentCradleId}/`,
              "info"
            );
          } else {
            console.error(
              `[CradleScanner] ❌ Network download failed:`,
              response?.error
            );
            this.showNotification(
              `❌ Download failed: ${response?.error}`,
              "error"
            );
          }
        }
      );
    } catch (error) {
      console.error("[CradleScanner] ❌ Network file download error:", error);
      throw error;
    }
  }

  // ✅ METODA - Fallback instrukcje dla pliku emisyjnego
  async fallbackEmissionFileInstructions(searchPath) {
    // Skopiuj ścieżkę do schowka
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(searchPath);
        this.showNotification(`📋 Path copied to clipboard!`, "success");
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = searchPath;
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        this.showNotification(`📋 Path copied to clipboard!`, "success");
      }
    } catch (error) {
      console.log("[CradleScanner] Clipboard failed:", error);
    }

    // Pokaż szczegółowe instrukcje
    this.showNotification(`🎯 Manual Instructions:`, "info");
    this.showNotification(`📁 Path: ${searchPath}`, "info");
    this.showNotification(`🔍 Find file: ${this.currentCradleId}*.*`, "info");
    this.showNotification(
      `💾 Copy to: Downloads/${this.currentCradleId}/`,
      "info"
    );

    // Alert z instrukcjami
    setTimeout(() => {
      alert(
        `🎬 EMISSION FILE - Manual Copy Needed\n\n` +
          `Path: ${searchPath}\n\n` +
          `Instructions:\n` +
          `1. Open Finder and navigate to above path\n` +
          `2. Look for file starting with: ${this.currentCradleId}\n` +
          `3. Copy the file to Downloads/${this.currentCradleId}/ folder\n\n` +
          `Path has been copied to clipboard.`
      );
    }, 1000);
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
