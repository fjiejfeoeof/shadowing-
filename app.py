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
    # CPU/GPUを自動判別し、軽量なbaseモデルを読み込みます
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 画面設定 ---
st.set_page_config(page_title="Ultimate Shadowing Studio", layout="wide")
st.title("🎙️ My Shadowing Library")

st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. ファイル管理システム ---
st.subheader("📁 練習用ファイルをアップロード")
# 拡張機能等で保存したファイルをここにドロップします
uploaded_files = st.file_uploader("音声または動画を並べましょう（複数可）", type=["mp3", "mp4", "wav", "m4a"], accept_multiple_files=True)

if uploaded_files:
    file_names = [f.name for f in uploaded_files]
    selected_name = st.selectbox("練習するファイルを選択", file_names)
    sec = st.number_input("練習する秒数", min_value=5, max_value=60, value=15)
    
    target_file = next(f for f in uploaded_files if f.name == selected_name)

    # 選択ファイルが変わった場合のみ解析を実行
    if 'current_ana_file' not in st.session_state or st.session_state.current_ana_file != selected_name:
        with st.spinner(f"{selected_name} を解析中..."):
            try:
                # 一時保存
                with open("temp_raw", "wb") as f:
                    f.write(target_file.getbuffer())

                # ffmpegで変換（16kHzモノラルwavに固定）
                subprocess.run(["ffmpeg", "-i", "temp_raw", "-ss", "0", "-t", str(sec), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "temp_audio.wav", "-y"], check=True, capture_output=True)

                # 文字起こし
                segments, _ = model.transcribe("temp_audio.wav", word_timestamps=True, language="en")
                
                # データを保存
                st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
                with open("temp_audio.wav", "rb") as f:
                    st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                
                st.session_state.current_ana_file = selected_name

            except Exception as e:
                st.error(f"解析エラー: {e}")

    # --- 4. 練習プレイヤー & 録音システム ---
    if 'master_data' in st.session_state and 'audio_b64' in st.session_state:
        sub_html = "".join([f'<span id="w{i}" style="font-size:24px; font-weight:bold; padding:4px 8px; color:white; border-radius:4px; transition: 0.1s; display:inline-block;">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        json_data = json.dumps(st.session_state.master_data)
        
        html_code = f"""
            <div style="background:#111; padding:30px; border-radius:15px; text-align:center; color:white; font-family:sans-serif;">
                <div id="status" style="color:#00f2fe; margin-bottom:15px; font-weight:bold;">Ready</div>
                <div id="script" style="background:#1a1a1a; padding:30px; border-radius:10px; line-height:3.0; margin-bottom:20px; min-height:150px;">{sub_html}</div>
                <audio id="player" src="data:audio/wav;base64,{st.session_state.audio_b64}"></audio>
                <div style="display: flex; justify-content: center; gap: 15px;">
                    <button onclick="playOnly()" style="padding:15px 35px; border-radius:30px; background:#27ae60; color:white; border:none; font-weight:bold; cursor:pointer; font-size:16px;">🔁 Listen</button>
                    <button id="recBtn" onclick="toggleRec()" style="padding:15px 35px; border-radius:30px; background:#e74c3c; color:white; border:none; font-weight:bold; cursor:pointer; font-size:16px;">🎙️ Start Shadowing</button>
                </div>
            </div>
            <script>
                const audio = document.getElementById('player');
                const masterData = {json_data};
                const status = document.getElementById('status');
                let mediaRecorder; let audioChunks = [];

                function playOnly() {{ audio.currentTime = 0; audio.play(); draw(); }}

                function draw() {{
                    const ct = audio.currentTime;
                    masterData.forEach((m, i) => {{
                        const el = document.getElementById('w' + i);
                        if (!el) return;
                        if (ct >= m.start - 0.2 && ct <= m.end) {{
                            el.style.color = "#000"; el.style.backgroundColor = "#f1c40f"; el.style.transform = "scale(1.1)";
                        }} else {{
                            el.style.color = ct > m.end ? "#555" : "#fff"; el.style.backgroundColor = "transparent"; el.style.transform = "scale(1.0)";
                        }}
                    }});
                    if (!audio.paused) requestAnimationFrame(draw);
                }}

                async function toggleRec() {{
                    const btn = document.getElementById('recBtn');
                    if (!mediaRecorder || mediaRecorder.state === "inactive") {{
                        const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                        mediaRecorder = new MediaRecorder(stream);
                        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                        mediaRecorder.onstop = () => {{
                            const blob = new Blob(audioChunks, {{ type: 'audio/wav' }});
                            const reader = new FileReader();
                            reader.readAsDataURL(blob);
                            reader.onloadend = () => {{ window.parent.postMessage({{type: 'UPLOAD_AUDIO', data: reader.result}}, '*'); }};
                            audioChunks = [];
                        }};
                        mediaRecorder.start(); audio.currentTime = 0; audio.play(); draw();
                        btn.innerText = "🛑 Stop & Score"; btn.style.background = "#95a5a6";
                        status.innerText = "🔴 Recording...";
                    }} else {{
                        mediaRecorder.stop(); audio.pause();
                        btn.innerText = "🎙️ Start Shadowing"; btn.style.background = "#e74c3c";
                        status.innerText = "Analyzing Result...";
                    }}
                }}
            </script>
        """
        st.components.v1.html(html_code, height=550)

        # --- 5. AI採点処理 ---
        # 録音データを受け取るための隠し入力
        audio_transport = st.text_input("TARGET_INPUT_FOR_AUDIO", key="audio_transport_input")
        st.markdown("""
            <style>div[data-testid="stTextInput"]:has(input[aria-label="TARGET_INPUT_FOR_AUDIO"]) { display: none; }</style>
            <script>
            window.addEventListener('message', function(event) {
                if (event.data.type === 'UPLOAD_AUDIO') {
                    const base64Data = event.data.data.split(',')[1];
                    const allInputs = window.parent.document.querySelectorAll('input');
                    for (let input of allInputs) {
                        if (input.getAttribute('aria-label') === 'TARGET_INPUT_FOR_AUDIO') {
                            input.value = base64Data;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                }
            });
            </script>
        """, unsafe_allow_html=True)

        if audio_transport and len(audio_transport) > 100:
            with st.spinner("AI採点中..."):
                try:
                    with open("user_rec.wav", "wb") as f:
                        f.write(base64.b64decode(audio_transport))
                    user_res, _ = model.transcribe("user_rec.wav", language="en", beam_size=1)
                    user_text = " ".join([s.text for s in user_res]).lower().strip()
                    
                    if user_text:
                        m_words = [m['word'].lower().strip('.,!?') for m in st.session_state.master_data]
                        u_words = user_text.split()
                        
                        st.subheader("Shadowing Result")
                        result_html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; background: #1a1a1a; padding: 20px; border-radius: 10px;">'
                        score = 0
                        for m_w in m_words:
                            is_match = any(difflib.SequenceMatcher(None, m_w, u_w.strip('.,!?')).ratio() > threshold for u_w in u_words)
                            color = "#2ecc71" if is_match else "#e74c3c"
                            if is_match: score += 1
                            result_html += f'<span style="color:{color}; font-size: 20px; font-weight: bold;">{m_w}</span>'
                        result_html += '</div>'
                        st.markdown(result_html, unsafe_allow_html=True)
                        st.metric("達成度", f"{int((score / len(m_words)) * 100)}%")
                    else:
                        st.warning("音声がうまく聞き取れませんでした。もう一度録音してみてください。")
                except Exception as e:
                    st.error(f"採点エラー: {e}")
