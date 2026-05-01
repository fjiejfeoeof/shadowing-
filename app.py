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

# --- 2. 画面構成 ---
st.set_page_config(page_title="Ultimate Shadowing Studio", layout="wide")
st.title("🎙️ Ultimate Shadowing Studio")

st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. URL入力形式 ---
url = st.text_input("YouTube または TED の URLを入力してください")
sec = st.number_input("練習する秒数", min_value=5, max_value=60, value=15)

if url:
    if 'current_url' not in st.session_state or st.session_state.current_url != url:
        with st.spinner("URLから音声を抽出・解析中..."):
            try:
                # yt-dlpを使用して音声をダウンロード (URL形式の肝)
                subprocess.run(["yt-dlp", "-x", "--audio-format", "wav", "-o", "temp_audio.wav", url], check=True)
                # 指定秒数にカット
                subprocess.run(["ffmpeg", "-i", "temp_audio.wav", "-t", str(sec), "-ar", "16000", "-ac", "1", "final_audio.wav", "-y"], check=True)
                
                segments, _ = model.transcribe("final_audio.wav", word_timestamps=True, language="en")
                st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
                
                with open("final_audio.wav", "rb") as f:
                    st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                st.session_state.current_url = url
            except Exception as e:
                st.error(f"解析エラー: {e}。yt-dlpがインストールされているか確認してください。")

    # --- 4. 視覚ガイドUI (URL形式で安定動作) ---
    if 'master_data' in st.session_state:
        subtitle_html = "".join([f'<span id="w{i}" class="word-span">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        
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
                        el.style.color = "#000"; el.style.backgroundColor = "#f1c40f"; 
                    } else {
                        el.style.color = ct > m.end ? "#666" : "#fff";
                        el.style.backgroundColor = "transparent";
                    }
                });
                if (!audio.paused) requestAnimationFrame(updateHighlight);
            }

            window.startListening = () => {
                btnContainer.innerHTML = "";
                audio.currentTime = 0; audio.play(); status.textContent = "👂 Listening..."; updateHighlight();
                audio.onended = () => {
                    status.textContent = "準備はいいですか？";
                    btnContainer.innerHTML = `
                        <button onclick="startListening()" class="btn-base" style="background:#444;">🔁 もう一度</button>
                        <button onclick="startShadowing()" class="btn-base" style="background:#e74c3c;">🚀 練習開始</button>
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
        final_html = html_template.replace("__SUBTITLE_HTML__", subtitle_html)\
                                  .replace("__AUDIO_B64__", st.session_state.audio_b64)\
                                  .replace("__JSON_DATA__", json.dumps(st.session_state.master_data))
        st.components.v1.html(final_html, height=550)

        # (以下、非表示入力欄と採点ロジックは前回同様に維持)
