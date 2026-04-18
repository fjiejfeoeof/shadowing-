import streamlit as st
import base64
import torch
from faster_whisper import WhisperModel
import yt_dlp
import os

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

# --- 3. URL入力セクション ---
url = st.text_input("YouTube または TED の URLを入力してください")
sec = st.number_input("練習する秒数", min_value=5, max_value=60, value=15)

if url:
    if 'audio_b64' not in st.session_state or st.session_state.get('last_url') != url:
        with st.spinner("音声を解析中..."):
            try:
                if os.path.exists("temp_audio.wav"):
                    os.remove("temp_audio.wav")

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'wav','preferredquality': '192'}],
                    'outtmpl': 'temp_audio',
                    'quiet': True,
                    'external_downloader': 'ffmpeg',
                    'external_downloader_args': ['-ss', '0', '-t', str(sec), '-loglevel', 'error', '-force_keyframes_at_cuts']
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                segments, _ = model.transcribe("temp_audio.wav", word_timestamps=True, language="en")
                st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
                
                with open("temp_audio.wav", "rb") as f:
                    st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                st.session_state.last_url = url
            except Exception as e:
                st.error(f"Error: {e}")

    if 'master_data' in st.session_state:
        subtitle_html = "".join([f'<span id="w{i}" style="font-size:24px; font-weight:bold; display:inline-block; padding:2px 5px; color:white; transition:0.1s;">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        st.components.v1.html(f"""
            <div style="background:#111; padding:30px; border-radius:15px; text-align:center; color:white; font-family:sans-serif;">
                <div id="status" style="color:#00f2fe; margin-bottom:15px;">Ready</div>
                <div id="scriptArea" style="background:#1a1a1a; padding:25px; border-radius:10px; line-height:2.8;">{subtitle_html}</div>
                <audio id="player" src="data:audio/wav;base64,{st.session_state.audio_b64}"></audio>
                <button onclick="playDemo()" style="margin-top:25px; padding:15px 40px; border-radius:30px; background:#27ae60; color:white; border:none; font-weight:bold; cursor:pointer;">🔁 Listen & Guide</button>
            </div>
            <script>
                const audio = document.getElementById('player');
                const masterData = {st.session_state.master_data};
                function playDemo() {{ audio.currentTime = 0; audio.play(); draw(); }}
                function draw() {{
                    const ct = audio.currentTime;
                    masterData.forEach((m, i) => {{
                        const el = document.getElementById('w' + i);
                        if (ct >= m.start - 0.75 && ct < m.start) {{ el.style.color = "#00f2fe"; }}
                        else if (ct >= m.start && ct <= m.end) {{ el.style.color = "#f1c40f"; el.style.transform = "scale(1.2)"; }}
                        else {{ el.style.color = ct > m.end ? "#555" : "white"; el.style.transform = "scale(1.0)"; }}
                    }});
                    if (!audio.paused) requestAnimationFrame(draw);
                }}
            </script>
        """, height=550)
