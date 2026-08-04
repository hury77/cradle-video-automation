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
    systemErrors: "System Errors",
    viewLogs: "View logs",
    noSystemErrors: "No system errors reported.",
    systemNotifications: "System Notifications",
    
    // Video Comparison
    dashboardBreadcrumb: "Dashboard",
    acceptanceVideo: "Acceptance Video",
    emissionVideo: "Emission Video",
    dragDropAcceptance: "Drag and drop Acceptance video",
    dragDropEmission: "Drag and drop Emission video",
    supportsFormats: "Supports MP4, MOV, MXF",
    videoDifferences: "Video Differences",
    audioDifferences: "Audio Differences",
    paused: "PAUSED",
    playing: "PLAYING",
    
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
  }
};
