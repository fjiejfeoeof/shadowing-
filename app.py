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
    # 実行環境に合わせてCPU/GPUを自動選択
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 画面構成 ---
st.set_page_config(page_title="Ultimate Shadowing Studio", layout="wide")
st.title("🎙️ Ultimate Shadowing Studio")

st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
# 判定の厳しさを調整
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. ファイルアップロード ---
uploaded_files = st.file_uploader("音声をアップロード", type=["mp3", "mp4", "wav", "m4a"], accept_multiple_files=True)

if uploaded_files:
    file_names = [f.name for f in uploaded_files]
    selected_name = st.selectbox("練習するファイルを選択", file_names)
    sec = st.number_input("練習秒数", min_value=5, max_value=60, value=15)
    
    target_file = next(f for f in uploaded_files if f.name == selected_name)

    # 初回またはファイル変更時のみ解析を実行
    if 'current_ana_file' not in st.session_state or st.session_state.current_ana_file != selected_name:
        with st.spinner("AIが音声を解析中..."):
            with open("temp_raw", "wb") as f:
                f.write(target_file.getbuffer())
            # ffmpegを使用して解析に最適な形式へ変換
            subprocess.run(["ffmpeg", "-i", "temp_raw", "-ss", "0", "-t", str(sec), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "temp_audio.wav", "-y"], capture_output=True)
            
            segments, _ = model.transcribe("temp_audio.wav", word_timestamps=True, language="en")
            st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
            
            with open("temp_audio.wav", "rb") as f:
                st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
            st.session_state.current_ana_file = selected_name

    # --- 4. フロントエンドUI (ここが解決の鍵) ---
    if 'master_data' in st.session_state:
        subtitle_html = "".join([f'<span id="w{i}" class="word-span">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        
        # 波括弧の衝突を防ぐため、Pythonの変数は __名__ で定義
        html_template = """
        <style>
            .word-span { font-size:24px; font-weight:bold; display:inline-block; padding:2px 8px; transition:0.1s; color:white; border-radius:4px; }
            .btn-base { padding:15px 35px; border-radius:50px; cursor:pointer; font-weight:bold; border:none; color:white; margin:10px; font-size:16px; }
        </style>
        <div style="background:#111; padding:40px; border-radius:20px; text-align:center; color:white; font-family:sans-serif;">
            <div id="status" style="color:#00f2fe; font-weight:bold; margin-bottom:20px; font-size:22px;">Ready</div>
            <div id="scriptArea" style="background:#1a1a1a; padding:30px; border-radius:15px; text-align:left; line-height:3.0; margin-bottom:25px;">__SUBTITLE_HTML__</div>
            <div id="btnContainer" style="display:flex; justify-content:center;">
                <button onclick="startListening()" class="btn-base" style="background:#27ae60;">🎧 Listen First (お手本を聴く)</button>
            </div>
        </div>
        <audio id="mainAudio" src="data:audio/wav;base64,__AUDIO_B64__"></audio>

        <script>
            const masterData = __JSON_DATA__;
            const audio = document.getElementById('mainAudio');
            const status = document.getElementById('status');
            const btnContainer = document.getElementById('btnContainer');
            let recorder, chunks = [];

            function updateHighlight() {
                const ct = audio.currentTime;
                masterData.forEach((m, i) => {
                    const el = document.getElementById('w' + i);
                    if (!el) return;
                    if (ct >= m.start - 0.75 && ct < m.start) {
                        el.style.color = "#00f2fe"; // 水色予兆
                    } else if (ct >= m.start && ct <= m.end) {
                        el.style.color = "#000"; el.style.backgroundColor = "#f1c40f"; // 発音中(黄色)
                        el.style.transform = "scale(1.2)";
                    } else {
                        el.style.color = ct > m.end ? "#666" : "#fff";
                        el.style.backgroundColor = "transparent";
                        el.style.transform = "scale(1.0)";
                    }
                });
                if (!audio.paused) requestAnimationFrame(updateHighlight);
            }

            window.startListening = () => {
                btnContainer.innerHTML = "";
                audio.currentTime = 0; audio.play(); status.textContent = "👂 Listening..."; updateHighlight();
                audio.onended = () => {
                    status.textContent = "リスニング完了。本番へ進みますか？";
                    btnContainer.innerHTML = `
                        <button onclick="startListening()" class="btn-base" style="background:#444;">🔁 もう一度聴く</button>
                        <button onclick="startShadowing()" class="btn-base" style="background:#e74c3c;">🚀 OK(練習開始)</button>
                    `;
                };
            };

            window.startShadowing = async () => {
                btnContainer.innerHTML = "";
                status.textContent = "🔴 RECORDING...";
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                recorder = new MediaRecorder(stream);
                recorder.ondataavailable = e => chunks.push(e.data);
                recorder.onstop = () => {
                    const reader = new FileReader();
                    reader.readAsDataURL(new Blob(chunks));
                    reader.onloadend = () => window.parent.postMessage({type: 'UPLOAD_AUDIO', data: reader.result}, '*');
                    chunks = [];
                };
                audio.currentTime = 0; audio.play(); recorder.start(); updateHighlight();
                audio.onended = () => { recorder.stop(); status.textContent = "Analyzing..."; };
            };
        </script>
        """
        # 値を安全に置換して描画
        final_html = html_template.replace("__SUBTITLE_HTML__", subtitle_html)\
                                  .replace("__AUDIO_B64__", st.session_state.audio_b64)\
                                  .replace("__JSON_DATA__", json.dumps(st.session_state.master_data))
        st.components.v1.html(final_html, height=550)

        # --- 5. 採点バックエンド ---
        # 通信用の入力欄をCSSで隠す
        st.markdown("<style>div[data-testid='stTextInput']:has(input[aria-label='hidden_comm']) { display: none; }</style>", unsafe_allow_html=True)
        comm_input = st.text_input("hidden_comm", key="comm_input", label_visibility="collapsed")

        st.markdown("""
            <script>
            window.addEventListener('message', function(e) {
                if (e.data.type === 'UPLOAD_AUDIO') {
                    const input = window.parent.document.querySelector('input[aria-label="hidden_comm"]');
                    if (input) {
                        input.value = e.data.data.split(',')[1];
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }
            });
            </script>
        """, unsafe_allow_html=True)

        if comm_input and len(comm_input) > 100:
            with st.spinner("採点中..."):
                with open("user.wav", "wb") as f: f.write(base64.b64decode(comm_input))
                res, _ = model.transcribe("user.wav", language="en")
                user_text = " ".join([s.text for s in res]).lower()
                m_words = [m['word'].lower().strip('.,!?') for m in st.session_state.master_data]
                u_words = user_text.split()
                
                score = 0
                res_html = '<div style="display:flex; flex-wrap:wrap; gap:10px; background:#1a1a1a; padding:20px; border-radius:10px;">'
                for m_w in m_words:
                    match = any(difflib.SequenceMatcher(None, m_w, u_w.strip('.,!?')).ratio() > threshold for u_w in u_words)
                    color = "#2ecc71" if match else "#e74c3c"
                    if match: score += 1
                    res_html += f'<span style="color:{color}; font-size:20px; font-weight:bold;">{m_w}</span>'
                st.markdown(res_html + '</div>', unsafe_allow_html=True)
                st.metric("Score", f"{int((score/len(m_words))*100)}%")
