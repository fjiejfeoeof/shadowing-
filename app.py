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
    # GPUがあれば使い、なければCPUで動かします
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 画面設定 ---
st.set_page_config(page_title="Shadowing Studio AI", layout="wide")
st.title("🎙️ Local File Shadowing Studio")

st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. ファイルアップロード & 解析 ---
st.subheader("📁 練習したいファイルをアップロード")
uploaded_file = st.file_uploader("動画または音声ファイルを選択してください (mp4, mp3, wavなど)", type=["mp4", "mp3", "wav", "m4a"])
sec = st.number_input("練習する秒数 (冒頭からこの秒数を切り出します)", min_value=5, max_value=60, value=15)

if uploaded_file is not None:
    # ファイル名が変わった場合のみ、再解析を行う
    if 'last_uploaded_name' not in st.session_state or st.session_state.last_uploaded_name != uploaded_file.name:
        with st.spinner("AIが音声を解析中..."):
            try:
                # 1. アップロードされたファイルを一時保存
                raw_path = f"raw_{uploaded_file.name}"
                with open(raw_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # 2. 練習用にカット＆変換 (ffmpeg)
                output_file = "temp_audio.wav"
                cmd = ["ffmpeg", "-i", raw_path, "-ss", "0", "-t", str(sec), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_file, "-y"]
                subprocess.run(cmd, check=True, capture_output=True)

                # 3. 文字起こし実行
                segments, _ = model.transcribe(output_file, word_timestamps=True, language="en")
                
                # 4. セッションに保存
                st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
                with open(output_file, "rb") as f:
                    st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                
                st.session_state.last_uploaded_name = uploaded_file.name
                
                # 使い終わった生ファイルは削除
                if os.path.exists(raw_path): os.remove(raw_path)

            except Exception as e:
                st.error(f"解析エラー: {e}")

    # --- 4. ビジュアルガイド ---
    if 'master_data' in st.session_state:
        # 字幕HTMLの生成
        sub_html = "".join([f'<span id="w{i}" style="font-size:24px; font-weight:bold; padding:4px 8px; color:white; border-radius:4px; transition: 0.1s; display:inline-block;">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        json_data = json.dumps(st.session_state.master_data)
        
        html_code = f"""
            <div style="background:#111; padding:30px; border-radius:15px; text-align:center; color:white; font-family:sans-serif;">
                <div id="status" style="color:#00f2fe; margin-bottom:15px; font-weight:bold;">Ready</div>
                <div id="script" style="background:#1a1a1a; padding:30px; border-radius:10px; line-height:3.0; margin-bottom:20px; min-height:150px;">{sub_html}</div>
                <audio id="player" src="data:audio/wav;base64,{st.session_state.audio_b64}"></audio>
                <div style="display: flex; justify-content: center; gap: 15px;">
                    <button onclick="playOnly()" style="padding:15px 35px; border-radius:30px; background:#27ae60; color:white; border:none; font-weight:bold; cursor:pointer; font-size:16px;">🔁 Listen</button>
                    <button id="recBtn" onclick="toggleRec()" style="padding:15px 35px; border-radius:30px; background:#e74c3c; color:white; border:none; font-weight:bold; cursor:pointer; font-size:16px;">🎙️ Start</button>
                </div>
            </div>
            <script>
                const audio = document.getElementById('player');
                const masterData = {json_data};
                // (JavaScriptの描画・録音ロジックは以前と同じ)
                // ... 略 ...
            </script>
        """
        # ※以前と同じJSロジックが含まれます
        st.components.v1.html(html_code, height=500)

        # (以下、採点システムは以前と同じ)
