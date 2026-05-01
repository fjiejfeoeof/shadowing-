import streamlit as st
import base64
import torch
from faster_whisper import WhisperModel
import os
import difflib
import json
import subprocess

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 画面設定 ---
st.set_page_config(page_title="Ultimate Shadowing Studio", layout="wide")
st.title("🎙️ Ultimate Shadowing Studio")

st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. ファイルアップロード ---
uploaded_files = st.file_uploader("練習用ファイルをドロップ", type=["mp3", "mp4", "wav", "m4a"], accept_multiple_files=True)

if uploaded_files:
    file_names = [f.name for f in uploaded_files]
    selected_name = st.selectbox("ファイルを選択", file_names)
    sec = st.number_input("練習秒数", min_value=5, max_value=60, value=15)
    
    target_file = next(f for f in uploaded_files if f.name == selected_name)

    if 'current_ana_file' not in st.session_state or st.session_state.current_ana_file != selected_name:
        with st.spinner("解析中..."):
            with open("temp_raw", "wb") as f:
                f.write(target_file.getbuffer())
            subprocess.run(["ffmpeg", "-i", "temp_raw", "-ss", "0", "-t", str(sec), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "temp_audio.wav", "-y"], capture_output=True)
            segments, _ = model.transcribe("temp_audio.wav", word_timestamps=True, language="en")
            st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
            with open("temp_audio.wav", "rb") as f:
                st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
            st.session_state.current_ana_file = selected_name

    # --- 4. 視覚ガイドUI (水色予兆・リピート・二段階) ---
    if 'master_data' in st.session_state:
        subtitle_html = "".join([f'<span id="w{i}" class="word-span">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        
        html_template = """
        <style>
            .word-span { font-size:24px; font-weight:bold; display:inline-block; padding:2px 8px; transition:0.1s; transform-origin:center; color:white; border-radius:4px; }
            .btn-base { padding:15px 30px; border-radius:50px; cursor:pointer; font-weight:bold; border:none; color:white; margin:10px; font-size:16px; transition:0.2s; }
            .btn-base:hover { opacity: 0.8; transform: scale(1.05); }
        </style>
        <div style="background:#111; padding:40px; border-radius:20px; text-align:center; color:white; font-family:sans-serif;">
            <div id="status" style="color:#00f2fe; font-weight:bold; margin-bottom:20px; font-size:22px;">Ready</div>
            <div id="scriptArea" style="background:#1a1a1a; padding:30px; border-radius:15px; text-align:left; line-height:3.0; margin-bottom:25px;">__SUBTITLE_HTML__</div>
            <div id="btnContainer" style="display:flex; justify-content:center; min-height:60px;">
                <button onclick="startListening()" class="btn-base" style="background:#27ae60;">🎧 Listen First (お手本を聴く)</button>
            </div>
        </div>
        <audio id="mainAudio" src="data:audio/wav;base64,__AUDIO_B64__"></audio>

        <script>
            const masterData = __JSON_DATA__;
            const audio = document.getElementById('mainAudio');
            const status = document.getElementById('status');
            const btnContainer = document.getElementById('btnContainer');
            let recorder, chunks = [], animId;

            function updateHighlight() {
                const ct = audio.currentTime;
                masterData.forEach((m, i) => {
                    const el = document.getElementById('w' + i);
                    if (!el) return;
                    if (ct >= m.start - 0.75 && ct < m.start) {
                        el.style.color = "#00f2fe"; // 水色予兆
                        el.style.backgroundColor = "transparent";
                        el.style.transform = (ct >= m.start - 0.1) ? "scale(1.15)" : "scale(1.0)";
                    } else if (ct >= m.start && ct <= m.end) {
                        el.style.color = "#000"; el.style.backgroundColor = "#f1c40f"; // 本番黄色
                        el.style.transform = "scale(1.2)";
                    } else {
                        el.style.color = ct > m.end ? "#666" : "#fff";
                        el.style.backgroundColor = "transparent";
                        el.style.transform = "scale(1.0)";
                    }
                });
                if (!audio.paused) animId = requestAnimationFrame(updateHighlight);
            }

            window.startListening = () => {
                btnContainer.innerHTML = "";
                audio.currentTime = 0; audio.play(); status.textContent = "👂 Listening..."; updateHighlight();
                audio.onended = () => {
                    status.textContent = "リスニング完了。本番へ進みますか？";
                    btnContainer.innerHTML = `
                        <button onclick="startListening()" class="btn-base" style="background:#444;">🔁 もう一度聴く</button>
                        <button onclick="prepareShadowing()" class="btn-base" style="background:#e74c3c;">🚀 OK(練習開始)</button>
                    `;
                };
            };

            window.prepareShadowing = async () => {
                btnContainer.innerHTML = "";
                let count = 3;
                const timer = setInterval(async () => {
                    status.textContent = "準備: " + count;
                    if (count-- <= 0) {
                        clearInterval(timer);
                        startShadowing();
                    }
                }, 1000);
            };

            async body startShadowing() {
                status.textContent = "🔴 RECORDING...";
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                recorder = new MediaRecorder(stream);
                recorder.ondataavailable = e => chunks.push(e.data);
                recorder.onstop = () => {
                    const blob = new Blob(chunks, { type: 'audio/wav' });
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        window.parent.postMessage({type: 'UPLOAD_AUDIO', data: reader.result}, '*');
                    };
                    chunks = [];
                };
                audio.currentTime = 0; audio.play(); recorder.start(); updateHighlight();
                audio.onended = () => {
                    recorder.stop();
                    status.textContent = "Analyzing...";
                };
            }
        </script>
        """
        # 値の埋め込み
        final_html = html_template.replace("__SUBTITLE_HTML__", subtitle_html)\
                                  .replace("__AUDIO_B64__", st.session_state.audio_b64)\
                                  .replace("__JSON_DATA__", json.dumps(st.session_state.master_data))
        st.components.v1.html(final_html, height=550)

        # --- 5. 採点処理用隠し通信 ---
        audio_transport = st.text_input("HiddenInput", key="audio_transport_input", label_visibility="collapsed")
        st.markdown("""
            <script>
            window.addEventListener('message', function(event) {
                if (event.data.type === 'UPLOAD_AUDIO') {
                    const base64Data = event.data.data.split(',')[1];
                    const input = window.parent.document.querySelector('input[aria-label="HiddenInput"]');
                    if (input) {
                        input.value = base64Data;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }
            });
            </script>
        """, unsafe_allow_html=True)

        if audio_transport and len(audio_transport) > 100:
            with st.spinner("AI採点中..."):
                with open("user_rec.wav", "wb") as f:
                    f.write(base64.b64decode(audio_transport))
                user_res, _ = model.transcribe("user_rec.wav", language="en")
                user_text = " ".join([s.text for s in user_res]).lower().strip()
                
                if user_text:
                    m_words = [m['word'].lower().strip('.,!?') for m in st.session_state.master_data]
                    u_words = user_text.split()
                    st.subheader("Shadowing Result")
                    result_html = '<div style="display:flex; flex-wrap:wrap; gap:10px; background:#1a1a1a; padding:20px; border-radius:10px;">'
                    score = 0
                    for m_w in m_words:
                        is_match = any(difflib.SequenceMatcher(None, m_w, u_w.strip('.,!?')).ratio() > threshold for u_w in u_words)
                        color = "#2ecc71" if is_match else "#e74c3c"
                        if is_match: score += 1
                        result_html += f'<span style="color:{color}; font-size:20px; font-weight:bold;">{m_w}</span>'
                    result_html += '</div>'
                    st.markdown(result_html, unsafe_allow_html=True)
                    st.metric("達成度", f"{int((score / len(m_words)) * 100)}%")
