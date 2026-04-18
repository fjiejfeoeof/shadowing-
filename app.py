import streamlit as st
import base64
import torch
from faster_whisper import WhisperModel
import yt_dlp
import os
import difflib

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

# --- 3. URL入力 & 音声解析セクション ---
url = st.text_input("YouTube または TED の URLを入力してください")
sec = st.number_input("練習する秒数", min_value=5, max_value=60, value=15)

if url:
    if 'audio_b64' not in st.session_state or st.session_state.get('last_url') != url:
        with st.spinner("お手本音声を解析中..."):
            try:
                if os.path.exists("temp_audio.wav"): os.remove("temp_audio.wav")
                if os.path.exists("temp_full.wav"): os.remove("temp_full.wav")

                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'wav','preferredquality': '192'}],
                    'outtmpl': 'temp_full', 'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
                
                os.system(f"ffmpeg -i temp_full.wav -ss 0 -t {sec} -c copy temp_audio.wav -y")
                
                segments, _ = model.transcribe("temp_audio.wav", word_timestamps=True, language="en")
                st.session_state.master_data = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
                
                with open("temp_audio.wav", "rb") as f:
                    st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                st.session_state.last_url = url
            except Exception as e: st.error(f"Error: {e}")

    # --- 4. メインUI (お手本再生 & マイク録音) ---
    if 'master_data' in st.session_state:
        st.subheader("Visual Guide & Recording")
        
        # 字幕HTML
        sub_html = "".join([f'<span id="w{i}" style="font-size:24px; font-weight:bold; padding:2px 5px; color:white;">{m["word"]}</span> ' for i, m in enumerate(st.session_state.master_data)])
        
        st.components.v1.html(f"""
            <div style="background:#111; padding:25px; border-radius:15px; text-align:center; color:white; font-family:sans-serif;">
                <div id="status" style="color:#00f2fe; margin-bottom:10px;">Ready</div>
                <div id="script" style="background:#1a1a1a; padding:20px; border-radius:10px; line-height:2.5; margin-bottom:20px;">{sub_html}</div>
                <audio id="player" src="data:audio/wav;base64,{st.session_state.audio_b64}"></audio>
                
                <button id="playBtn" onclick="playDemo()" style="padding:12px 25px; border-radius:25px; background:#27ae60; color:white; border:none; font-weight:bold; cursor:pointer; margin:5px;">🔁 Listen & Guide</button>
                <button id="recBtn" onclick="toggleRec()" style="padding:12px 25px; border-radius:25px; background:#e74c3c; color:white; border:none; font-weight:bold; cursor:pointer; margin:5px;">🎤 Record Start</button>
            </div>

            <script>
                const audio = document.getElementById('player');
                const masterData = {st.session_state.master_data};
                let mediaRecorder; let audioChunks = [];

                function playDemo() {{
                    audio.currentTime = 0; audio.play(); draw();
                }}

                function draw() {{
                    const ct = audio.currentTime;
                    masterData.forEach((m, i) => {{
                        const el = document.getElementById('w' + i);
                        if (ct >= m.start - 0.75 && ct < m.start) el.style.color = "#00f2fe";
                        else if (ct >= m.start && ct <= m.end) {{ el.style.color = "#f1c40f"; el.style.transform = "scale(1.2)"; }}
                        else {{ el.style.color = ct > m.end ? "#555" : "white"; el.style.transform = "scale(1.0)"; }}
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
                            reader.onloadend = () => {{
                                window.parent.postMessage({{type: 'UPLOAD_AUDIO', data: reader.result}}, '*');
                            }};
                            audioChunks = [];
                        }};
                        mediaRecorder.start();
                        btn.innerText = "🛑 Stop & Score"; btn.style.background = "#95a5a6";
                    }} else {{
                        mediaRecorder.stop();
                        btn.innerText = "🎤 Record Start"; btn.style.background = "#e74c3c";
                    }}
                }}
            </script>
        """, height=450)

        # --- 5. 自動採点ロジック ---
        # JSからの音声データを受け取る仕組み
        import streamlit.components.v1 as components
        st.markdown("""<script>
            window.addEventListener('message', function(event) {
                if (event.data.type === 'UPLOAD_AUDIO') {
                    const base64Data = event.data.data.split(',')[1];
                    const input = window.parent.document.querySelector('input[aria-label="audio_data_transport"]');
                    input.value = base64Data;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        </script>""", unsafe_allow_html=True)
        
        audio_data = st.text_input("audio_data_transport", label_visibility="collapsed")
        
        if audio_data:
            with st.spinner("あなたの声をAIが採点中..."):
                with open("user_rec.wav", "wb") as f:
                    f.write(base64.b64decode(audio_data))
                
                # ユーザーの音声をテキスト化
                user_res, _ = model.transcribe("user_rec.wav", language="en")
                user_text = " ".join([s.text for s in user_res]).lower().strip()
                master_text = " ".join([m['word'] for m in st.session_state.master_data]).lower().strip()
                
                # 単語ごとに比較してハイライト
                m_words = master_text.split()
                u_words = user_text.split()
                
                st.subheader("Scoring Result")
                cols = st.columns(len(m_words))
                score = 0
                for i, m_w in enumerate(m_words):
                    # 類似度判定
                    is_match = any(difflib.SequenceMatcher(None, m_w, u_w).ratio() > threshold for u_w in u_words)
                    color = "#2ecc71" if is_match else "#e74c3c"
                    if is_match: score += 1
                    with cols[i % 10]: # 10単語ごとに改行っぽく表示
                        st.markdown(f"<p style='color:{color}; font-weight:bold; font-size:20px;'>{m_w}</p>", unsafe_allow_html=True)
                
                final_score = int((score / len(m_words)) * 100)
                st.metric("シャドーイング達成度", f"{final_score}%")
                if final_score > 80: st.balloons()
