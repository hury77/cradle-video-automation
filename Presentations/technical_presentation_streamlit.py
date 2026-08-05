import streamlit as st

# Set page config
st.set_page_config(
    page_title="NVC | Technical Intelligence Documentation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
PREMIUM_IMG = "/Users/hubert.rycaj/.gemini/antigravity/brain/f2448fed-990d-4ef5-9bf8-11b833cf445f/premium_ai_server_core_1777386429202.png"

# CSS: Technical Dark Theme
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;700&family=Inter:wght@400;700;800&display=swap');
    
    .stApp {
        background-color: #0b0e14;
        color: #d1d5db;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers */
    h1 { font-size: 3rem !important; font-weight: 800 !important; color: #00d2ff !important; margin-bottom: 20px !important; }
    h2 { font-size: 2rem !important; color: #ffffff !important; border-bottom: 1px solid #1e293b; padding-bottom: 10px; }
    h3 { font-size: 1.4rem !important; color: #38bdf8 !important; }
    
    /* Body */
    p, li, div { font-size: 1.15rem !important; line-height: 1.6 !important; }
    code { font-family: 'Fira Code', monospace !important; background-color: #1e293b !important; padding: 2px 6px !important; border-radius: 4px; }
    
    /* Cards */
    .tech-card {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 35px;
        margin-top: 15px;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] { width: 350px !important; background-color: #030712 !important; border-right: 1px solid #1e293b; }
    
    /* Status indicators */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 700;
        background: #0ea5e9;
        color: white;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Sidebar
st.sidebar.image(PREMIUM_IMG, use_container_width=True)
st.sidebar.markdown("<br><h2 style='text-align:center;'>NVC TECH SPECS</h2>", unsafe_allow_html=True)

page = st.sidebar.radio("MODULES", [
    "📑 01. Architecture Overview",
    "🔌 02. Agent 1: Control Loop",
    "🎥 03. Video Ingestion & HWaccel",
    "🖼️ 04. Computer Vision Metrics",
    "🎵 05. Audio DSP & Separation",
    "🗣️ 06. STT & Linguistic Analysis",
    "🧠 07. Agent 2: Logic & Overrides",
    "⚡ 08. Optimization & RAM",
    "🖥️ 09. Deployment & Docker",
    "📈 10. Scalability Roadmap"
])

# --- PAGE 1: ARCHITECTURE OVERVIEW ---
if page == "📑 01. Architecture Overview":
    st.markdown("<span class='badge'>v4.0 Production Ready</span>", unsafe_allow_html=True)
    st.markdown("<h1>System Architecture</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Multi-Agent Orchestration</h2>
        <p>System oparty na asynchronicznej architekturze <b>Agent-Based</b> komunikującej się przez protokół <b>WebSocket (wss://)</b>.</p>
        <ul>
            <li><b>Agent 1 (Controller):</b> Warstwa peryferyjna. Inicjalizacja sesji, scrapowanie meta-danych Cradle, transport binarny.</li>
            <li><b>Agent 2 (Analyst):</b> Warstwa kognitywna. Przetwarzanie sygnałów, inferencja modeli AI, deterministyczny werdykt.</li>
            <li><b>Agent 3 (DevOps/Monitor):</b> (Conceptual) Monitoring metryk systemowych i auto-tuning progów czułości.</li>
        </ul>
        <br>
        <h3>Communication Stack:</h3>
        <code>JSON-RPC style actions | Binary Blobs | Asyncio Event Loop</code>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 2: AGENT 1: CONTROL LOOP ---
elif page == "🔌 02. Agent 1: Control Loop":
    st.markdown("<h1>Agent 1: Operation Layer</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Browser Extension & WebSocket Bridge</h2>
        <p>Wtyczka (Manifest v3) pełni rolę <b>Data Ingestora</b> działającego w kontekście DOM platformy Cradle.</p>
        <h3>Kluczowe funkcje techniczne:</h3>
        <ul>
            <li><b>DOM Mutation Observer:</b> Reagowanie na zmiany statusu "Final Proofreading".</li>
            <li><b>LocalStorage Persistence:</b> Śledzenie stanu automatyzacji między przeładowaniami strony.</li>
            <li><b>Cross-Tab Communication:</b> Koordynacja między kartą listy zadań a kartą detali assetu przez <code>storage event listener</code>.</li>
        </ul>
        <h3>Specyfikacja połączenia:</h3>
        <code>ws://localhost:8765/api/v1/control</code>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 3: VIDEO INGESTION & HWACCEL ---
elif page == "🎥 03. Video Ingestion & HWaccel":
    st.markdown("<h1>Media Processing Pipeline</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>FFmpeg Ingestion Engine</h2>
        <p>Przetwarzanie wideo opiera się na niskopoziomowym wykorzystaniu <b>FFmpeg</b> z akceleracją sprzętową.</p>
        <h3>Hardware Acceleration:</h3>
        <ul>
            <li><b>Apple Silicon:</b> Wykorzystanie <code>VideoToolbox</code> dla bezstratnego dekodowania.</li>
            <li><b>NVIDIA:</b> Obsługa <code>NVDEC/NVENC</code> (cuvid) dla środowisk serwerowych.</li>
        </ul>
        <h3>Technika "On-the-fly Scaling":</h3>
        <p>Aby uniknąć OOM (Out Of Memory) przy plikach 4K ProRes, klatki są skalowane do 1280px bezpośrednio w potoku FFmpeg:</p>
        <code>-vf scale=1280:1280:force_original_aspect_ratio=decrease</code>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 4: COMPUTER VISION METRICS ---
elif page == "🖼️ 04. Computer Vision Metrics":
    st.markdown("<h1>Visual Comparison Analytics</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Algorytmy Matematyczne</h2>
        <p>Porównanie wizualne wykorzystuje biblioteki <b>OpenCV</b> oraz <b>scikit-image</b>.</p>
        <ul>
            <li><b>SSIM (Structural Similarity Index):</b> Analiza luminancji, kontrastu i struktury. Próg akceptacji <code>S > 0.98</code>.</li>
            <li><b>MSE (Mean Squared Error):</b> Pomiar różnicy kwadratowej pikseli dla detekcji szumów.</li>
            <li><b>Pixel-Wise Diff Mask:</b> Generowanie mapy różnic (heatmaps) dla klatek o niskim podobieństwie.</li>
        </ul>
        <h3>Optymalizacja:</h3>
        <p>Porównanie odbywa się na klatkach kluczowych oraz próbkach losowych (GOP aware sampling).</p>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 5: AUDIO DSP & SEPARATION ---
elif page == "🎵 05. Audio DSP & Separation":
    st.markdown("<h1>Acoustic Intelligence</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Audio Stem Isolation & Loudness</h2>
        <p>Wykorzystujemy model <b>Facebook Demucs v4 (Hybrid Transformer)</b> do separacji źródeł dźwięku.</p>
        <ul>
            <li><b>Stem Separation:</b> Izolacja wokalu (Vocals) od podkładu (Music/Other) przed transkrypcją.</li>
            <li><b>LUFS Analysis (EBU R128):</b> Pomiar głośności zintegrowanej. Tolerancja <code>±0.5 LUFS</code>.</li>
            <li><b>Phase Check:</b> Weryfikacja korelacji fazowej między kanałami L/R.</li>
        </ul>
        <h3>Model AI:</h3>
        <code>htdemucs_ft (Fine-tuned hybrid model) running on CUDA/MPS</code>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 6: STT & LINGUISTIC ANALYSIS ---
elif page == "🗣️ 06. STT & Linguistic Analysis":
    st.markdown("<h1>Speech-To-Text (STT) Pipeline</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Transcription & String Metrics</h2>
        <p>Analiza tekstowa opiera się na modelu <b>OpenAI Whisper Large-v3</b>.</p>
        <ul>
            <li><b>Inference:</b> Wykorzystanie <code>faster-whisper</code> z kwantyzacją <code>int8</code> dla redukcji VRAM.</li>
            <li><b>Fuzzy Matching:</b> Algorytm Levenshteina do obliczania dystansu edycyjnego między skryptem a lektorem.</li>
            <li><b>Normalization:</b> Usuwanie znaków specjalnych i normalizacja liczb przed porównaniem.</li>
        </ul>
        <h3>Logika Fast-Path:</h3>
        <p>Jeśli Audio Similarity > 0.999, system pomija kosztowny proces STT.</p>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 7: AGENT 2: LOGIC & OVERRIDES ---
elif page == "🧠 07. Agent 2: Logic & Overrides":
    st.markdown("<h1>Agent 2: Decision Engine</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Deterministic Decision Layer</h2>
        <p>Agent 2 łączy wnioskowanie LLM z twardymi progami matematycznymi (Deterministic Overrides).</p>
        <h3>Logic Guardrails:</h3>
        <p>Nawet jeśli LLM sugeruje "APPROVE", system wymusi "REJECT/REVIEW" jeśli:</p>
        <ul>
            <li><b>Video Similarity < 0.98</b></li>
            <li><b>Loudness Diff > 1.0 LUFS</b></li>
            <li><b>STT Confidence < 0.7</b></li>
        </ul>
        <h3>LLM Reasoning:</h3>
        <code>Context injection: [Video_Metrics, Audio_Metrics, Transcription_Delta] -> Llama 3 Inference</code>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 8: OPTIMIZATION & RAM ---
elif page == "⚡ 08. Optimization & RAM":
    st.markdown("<h1>Resource Management</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>System Stability Optimizations</h2>
        <p>Projekt zorientowany na pracę w środowiskach o ograniczonej pamięci (MacBook Air / Standard Servers).</p>
        <ul>
            <li><b>Sequential Execution:</b> Moduły (Video, Demucs, Whisper) uruchamiane są po kolei, nigdy symultanicznie.</li>
            <li><b>Manual GC:</b> Wywoływanie <code>gc.collect()</code> i <code>torch.cuda.empty_cache()</code> po każdym module.</li>
            <li><b>Buffer Management:</b> Przetwarzanie strumieniowe zamiast ładowania całych plików do RAM.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 9: DEPLOYMENT & DOCKER ---
elif page == "🖥️ 09. Deployment & Docker":
    st.markdown("<h1>Enterprise Deployment</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Infrastructure Architecture</h2>
        <p>Aplikacja jest w pełni skonteneryzowana dla łatwego wdrożenia serwerowego.</p>
        <h3>Docker Stack:</h3>
        <ul>
            <li><b>Base Image:</b> <code>nvidia/cuda:12.1-runtime-ubuntu22.04</code></li>
            <li><b>Dependencies:</b> Python 3.10, FFmpeg, CUDA Toolkit.</li>
            <li><b>Volumes:</b> Mapowanie <code>/uploads</code> i <code>/results</code> na szybką macierz SSD.</li>
        </ul>
        <h3>Requirements:</h3>
        <code>NVIDIA Container Toolkit | 16GB+ System RAM | 8GB+ VRAM</code>
    </div>
    """, unsafe_allow_html=True)

# --- PAGE 10: SCALABILITY ROADMAP ---
elif page == "📈 10. Scalability Roadmap":
    st.markdown("<h1>Scaling Strategy</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class="tech-card">
        <h2>Future Development</h2>
        <ul>
            <li><b>Centralized DB:</b> Migracja z SQLite na PostgreSQL/Redis dla obsługi klastrów.</li>
            <li><b>Task Queue:</b> Wdrożenie Celery/RabbitMQ dla orkiestracji wielu Agentów Analitycznych.</li>
            <li><b>Dashboard:</b> Centralny monitor tokenów LLM i obciążenia GPU.</li>
        </ul>
        <p style="color:#00d2ff; text-align:center; font-weight:800; font-size:1.5rem; margin-top:40px;">READY FOR PRODUCTION DEPLOYMENT</p>
    </div>
    """, unsafe_allow_html=True)

# Sidebar Footer
st.sidebar.markdown("---")
st.sidebar.markdown("<small style='color:#475569'>Stack: Python, FastAPI, WebSockets, PyTorch, FFmpeg, Manifest v3</small>", unsafe_allow_html=True)
