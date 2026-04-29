import streamlit as st
import base64
import torch
from faster_whisper import WhisperModel
import yt_dlp
import os
import difflib
import json
import subprocess  # 追加：エラー検知を強化するため

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 画面設定 ---
st.set_page_config(page_title="Shadowing Studio AI", layout="wide")
st.title("🎙️ Ultimate Shadowing Studio")

st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. URL入力 & 音声解析 ---
url = st.text_input("YouTube または TED の URLを入力してください")
sec = st.number_input("練習する秒数", min_value=5, max_value=60, value=15)

if url:
    if 'audio_b64' not in st.session_state or st.session_state.get('last_url') != url:
        with st.spinner("お手本を準備中... (これには1〜2分かかる場合があります)"):
            try:
                # 一時ファイルの削除
                for f in ["temp_audio.wav", "temp_full.wav"]:
                    if os.path.exists(f): os.remove(f)

                # ダウンロード設定
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'nocheckcertificate': True,
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': 'temp_full', # 拡張子は自動で付く場合があるため注意
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                        'preferredquality': '192',
                    }],
                }

                # ダウンロード実行
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # ファイル名の確定（yt-dlpが .wav を自動付与するため）
                input_file = "temp_full.wav"
                output_file = "temp_audio.wav"

                if not os.path.exists(input_file):
                    st.error("音声の取得に失敗しました。URLが正しいか確認してください。")
                else:
                    # ffmpegでカット (subprocessを使って確実に実行)
                    cmd = ["ffmpeg", "-i", input_file, "-ss", "0", "-t", str(sec), "-c", "copy", output_file, "-y"]
                    subprocess.run(cmd, check=True, capture_output=True)

                    if os.path.exists(output_file):
                        # 文字起こし
                        segments, _ = model.transcribe(output_file, word_timestamps=True, language="en")
                        
                        # データ保存
                        st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
                        with open(output_file, "rb") as f:
                            st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                        st.session_state.last_url = url
                    else:
                        st.error("音声の切り出しに失敗しました。")

            except Exception as e:
                st.error(f"詳細なエラーが発生しました: {e}")

    # --- 4. ビジュアルガイド ---
    if 'master_data' in st.session_state:
        # (以下、以前のHTML/JavaScriptコードと同じ)
        sub_html = "".join([f'<span id="w{i}" style="font-size:24px; font-weight:bold; padding:4px 8px; color:white; border-radius:4px; transition: 0.1s; display:inline-block;">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        json_data = json.dumps(st.session_state.master_data)
        
        html_code = """
            <div style="background:#111; padding:30px; border-radius:15px; text-align:center; color:white; font-family:sans-serif;">
                <div id="status" style="color:#00f2fe; margin-bottom:15px; font-weight:bold;">Ready</div>
                <div id="script" style="background:#1a1a1a; padding:30px; border-radius:10px; line-height:3.0; margin-bottom:20px; min-height:150px;">SUBTITLE_HERE</div>
                <audio id="player" src="data:audio/wav;base64,AUDIO_B64_HERE"></audio>
                <div style="display: flex; justify-content: center; gap: 15px;">
                    <button onclick="playOnly()" style="padding:15px 35px; border-radius:30px; background:#27ae60; color:white; border:none; font-weight:bold; cursor:pointer; font-size:16px;">🔁 Listen (No Rec)</button>
                    <button id="recBtn" onclick="toggleRec()" style="padding:15px 35px; border-radius:30px; background:#e74c3c; color:white; border:none; font-weight:bold; cursor:pointer; font-size:16px;">🎙️ Start Shadowing</button>
                </div>
            </div>
            <script>
                const audio = document.getElementById('player');
                const masterData = JSON_DATA_HERE;
                const status = document.getElementById('status');
                let mediaRecorder; let audioChunks = [];
                function playOnly() { audio.currentTime = 0; audio.play(); draw(); }
                function draw() {
                    const ct = audio.currentTime;
                    masterData.forEach((m, i) => {
                        const el = document.getElementById('w' + i);
                        if (!el) return;
                        if (ct >= m.start - 0.75 && ct < m.start) el.style.color = "#00f2fe";
                        else if (ct >= m.start && ct <= m.end) {
                            el.style.color = "#000"; el.style.backgroundColor = "#f1c40f"; el.style.transform = "scale(1.15)";
                        } else {
                            el.style.color = ct > m.end ? "#555" : "#fff"; el.style.backgroundColor = "transparent"; el.style.transform = "scale(1.0)";
                        }
                    });
                    if (!audio.paused) requestAnimationFrame(draw);
                }
                async function toggleRec() {
                    const btn = document.getElementById('recBtn');
                    if (!mediaRecorder || mediaRecorder.state === "inactive") {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                        mediaRecorder.onstop = () => {
                            const blob = new Blob(audioChunks, { type: 'audio/wav' });
                            const reader = new FileReader();
                            reader.readAsDataURL(blob);
                            reader.onloadend = () => { window.parent.postMessage({type: 'UPLOAD_AUDIO', data: reader.result}, '*'); };
                            audioChunks = [];
                        };
                        mediaRecorder.start(); audio.currentTime = 0; audio.play(); draw();
                        btn.innerText = "🛑 Stop & Score"; btn.style.background = "#95a5a6";
                        status.innerText = "🔴 Recording & Playing...";
                    } else {
                        mediaRecorder.stop(); audio.pause();
                        btn.innerText = "🎙️ Start Shadowing"; btn.style.background = "#e74c3c";
                    }
                }
            </script>
        """.replace("SUBTITLE_HERE", sub_html).replace("AUDIO_B64_HERE", st.session_state.audio_b64).replace("JSON_DATA_HERE", json_data)
        st.components.v1.html(html_code, height=500)

        # --- 5. 採点システム (前回提示の通り) ---
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
                    if not user_text:
                        st.warning("音声が検出できませんでした。")
                    else:
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
                        final_score = int((score / len(m_words)) * 100)
                        st.metric("達成度", f"{final_score}%")
                        if final_score >= 80: st.balloons()
                except Exception as e:
                    st.error(f"採点エラー: {e}")
