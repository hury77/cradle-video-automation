// frontend/src/utils/translations.ts

export type Language = "PL" | "EN";

export const translations = {
  PL: {
    // Header & App Title
    appTitle: "New Video Compare",
    appSubtitle: "PROFESSIONAL VIDEO ANALYSIS PLATFORM",
    devBadge: "DEV",
    devTooltip: "Środowisko deweloperskie — zmiany nie wpływają na LIVE",

    // Navigation Tabs
    navJobs: "Zadania",
    navStats: "Statystyki",
    navKB: "Baza Wiedzy",
    navLogs: "Logi",

    // Notifications & System Status
    backendStatus: "Backend",
    wsStatus: "WS",
    decisionEngineLabel: "Silnik decyzji",
    systemErrors: "Błędy Systemowe",
    viewLogs: "Zobacz logi",
    noSystemErrors: "Brak zgłoszonych błędów systemowych.",
    systemNotifications: "Powiadomienia systemowe",

    // Video Comparison
    dashboardBreadcrumb: "Dashboard",
    acceptanceVideo: "Wideo Akceptacyjne (Acceptance)",
    emissionVideo: "Wideo Emisyjne (Emission)",
    dragDropAcceptance: "Przeciągnij i upuść wideo Acceptance",
    dragDropEmission: "Przeciągnij i upuść wideo Emission",
    supportsFormats: "Obsługuje MP4, MOV, MXF",
    videoDifferences: "Różnice Wideo",
    audioDifferences: "Różnice Audio",
    paused: "WSTRZYMANE",
    playing: "ODTWARZANIE",
    waveformClockAligned: "Waveform wyrównany do synchronizacji Clock",

    // Tools & Controls
    eyedropper: "Kroplomierz",
    ruler: "Linijka",
    takeScreenshot: "Zrzut Ekranu",
    exportPdf: "Raport PDF",
    reanalyze: "Ponowna Analiza",
    backToDashboard: "Powrót do Dashboardu",

    // Dashboard & Filters
    totalJobs: "Wszystkie Joby",
    successRate: "Skuteczność",
    activeJobs: "Aktywne Joby",
    avgTime: "Śr. czas analizy",
    searchPlaceholder: "Szukaj wg ID Cradle, nazwy lub klienta...",
    statusAll: "Wszystkie statusy",
    statusCompleted: "Ukończone",
    statusProcessing: "W trakcie",
    statusFailed: "Błąd",
    statusPending: "Oczekujące",
    createNewJob: "Stwórz nowy Job",

    // Verdicts
    verdictApprove: "AKCEPTACJA",
    verdictReject: "ODRZUCENIE",
    verdictReview: "REVIEW",

    // Report & Metryczka
    reportMetryczkaTitle: "RAPORT QA",
    cradleId: "Cradle ID",
    client: "Klient",
    dateCreated: "Data analizy",
    durationLabel: "Czas trwania",
    acceptanceFile: "Plik Akceptacyjny",
    emissionFile: "Plik Emisyjny",
    resolutionLabel: "Rozdzielczość",
    qaVerdict: "Werdykt QA",
    aiAnalystBadge: "AI Analyst (Agent 2) — decyzja automatyczna",
    deterministicRulesBadge: "Deterministic Rules Engine v1 — decyzja automatyczna",
    humanOverrideBadge: "Human override — decyzja zmieniona przez użytkownika QA",
    decisionRationale: "Uzasadnienie decyzji",
    originalDecisionRationale: "Pierwotne uzasadnienie decyzji (do wglądu)",
    overrideDecisionBtn: "Zmień decyzję",
    editDecisionBtn: "Edytuj decyzję",
    overridingDecisionBadge: "Zmiana werdyktu automatycznego",
    overrideReasonLabel: "Powód zmiany decyzji",
    overrideReasonHint: "dlaczego zmieniasz decyzję automatyczną?",
    overrideReasonPlaceholder: "np. nie wykryto zmiany logo przy 0:08",
    archivedDecisionSnapshot: "Zarchiwizowany snapshot decyzji",
    decisionDetailsBtn: "Szczegóły",
    kbSubtitle: "Historyczne decyzje QA i snapshoty.",
    kbJsonExportTitle: "Pełny eksport JSON ze snapshotami decyzji",
    frameAnalysis: "Analiza Różnic Klatek (Inspect Differences)",
    dialogueTimeline: "Oś Czasu Dialogów / Lektor",
    loudnessComparison: "Porównanie Głośności LUFS",
    overallMatch: "Zgodność Ogólna",
    openInspector: "Otwórz Interaktywny Inspektor",
    inspect: "Inspekcja",
    formatGif: "Obsługuje GIF, MP4, MOV, MXF",
  },
  EN: {
    // Header & App Title
    appTitle: "New Video Compare",
    appSubtitle: "PROFESSIONAL VIDEO ANALYSIS PLATFORM",
    devBadge: "DEV",
    devTooltip: "Development Environment — changes do not affect LIVE",

    // Navigation Tabs
    navJobs: "Jobs",
    navStats: "Stats",
    navKB: "KB",
    navLogs: "Logs",

    // Notifications & System Status
    backendStatus: "Backend",
    wsStatus: "WS",
    decisionEngineLabel: "Decision engine",
    systemErrors: "System Errors",
    viewLogs: "View logs",
    noSystemErrors: "No system errors reported.",
    systemNotifications: "System Notifications",

    // Video Comparison
    dashboardBreadcrumb: "Dashboard",
    acceptanceVideo: "Acceptance Video",
    emissionVideo: "Emission Video",
    dragDropAcceptance: "Drag and drop Acceptance video or GIF",
    dragDropEmission: "Drag and drop Emission video or GIF",
    supportsFormats: "Supports GIF, MP4, MOV, MXF",
    videoDifferences: "Video Differences",
    audioDifferences: "Audio Differences",
    paused: "PAUSED",
    playing: "PLAYING",
    waveformClockAligned: "Waveform aligned to Clock sync",

    // Tools & Controls
    eyedropper: "Eyedropper",
    ruler: "Ruler",
    takeScreenshot: "Take Screenshot",
    exportPdf: "Export PDF",
    reanalyze: "Re-analyze",
    backToDashboard: "Back to Dashboard",

    // Dashboard & Filters
    totalJobs: "Total Jobs",
    successRate: "Success Rate",
    activeJobs: "Active Jobs",
    avgTime: "Avg Processing Time",
    searchPlaceholder: "Search by Cradle ID, name or client...",
    statusAll: "All Statuses",
    statusCompleted: "Completed",
    statusProcessing: "Processing",
    statusFailed: "Failed",
    statusPending: "Pending",
    createNewJob: "Create New Job",

    // Verdicts
    verdictApprove: "APPROVE",
    verdictReject: "REJECT",
    verdictReview: "REVIEW",

    // Report & Metryczka
    reportMetryczkaTitle: "QA REPORT",
    cradleId: "Cradle ID",
    client: "Client",
    dateCreated: "Analysis Date",
    durationLabel: "Duration",
    acceptanceFile: "Acceptance File",
    emissionFile: "Emission File",
    resolutionLabel: "Resolution",
    qaVerdict: "QA Verdict",
    aiAnalystBadge: "AI Analyst (Agent 2) — automatic decision",
    deterministicRulesBadge: "Deterministic Rules Engine v1 — automatic decision",
    humanOverrideBadge: "Human override — decision changed by QA user",
    decisionRationale: "Decision rationale",
    originalDecisionRationale: "Original decision rationale (for reference)",
    overrideDecisionBtn: "Override decision",
    editDecisionBtn: "Edit decision",
    overridingDecisionBadge: "Overriding automatic verdict",
    overrideReasonLabel: "Override Reason",
    overrideReasonHint: "why are you changing the automatic decision?",
    overrideReasonPlaceholder: "e.g. logo change not detected at 0:08",
    archivedDecisionSnapshot: "Archived decision snapshot",
    decisionDetailsBtn: "Details",
    kbSubtitle: "Historical QA decisions and snapshots.",
    kbJsonExportTitle: "Full JSON export with decision snapshots",
    frameAnalysis: "Frame Differences Analysis (Inspect Differences)",
    dialogueTimeline: "Dialogue Timeline / Speech-to-Text",
    loudnessComparison: "Loudness Comparison (LUFS)",
    overallMatch: "Overall Match",
    openInspector: "Open Interactive Inspector",
    inspect: "Inspect",
    formatGif: "Supports GIF, MP4, MOV, MXF",
  }
};
