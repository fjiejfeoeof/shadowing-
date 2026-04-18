import streamlit as st
import base64
import torch
from faster_whisper import WhisperModel
import yt_dlp
import os

# --- 1. AIモデルの準備（キャッシュして高速化） ---
@st.cache_resource
def load_model():
    # CUDAが使えればGPU、なければCPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 画面設定 ---
st.set_page_config(page_title="Shadowing Studio AI", layout="wide")
st.title("🎙️ Ultimate Shadowing Studio")

# サイドバーで難易度設定
st.sidebar.header("Settings")
diff_mode = st.sidebar.selectbox("難易度", ["1: Easy", "2: Normal", "3: Hard"])
threshold = {"1: Easy": 0.8, "2: Normal": 0.4, "3: Hard": 0.2}[diff_mode]

# --- 3. URL入力セクション ---
url = st.text_input("YouTube または TED の URLを入力してください", placeholder="https://www.youtube.com/watch?v=...")
sec = st.number_input("練習する秒数", min_value=5, max_value=60, value=15)

if url:
    # 音声取得処理
    if 'audio_b64' not in st.session_state or st.session_state.get('last_url') != url:
        with st.spinner("音声を生成・解析中..."):
            try:
                # yt-dlp設定
           ydl_opts = {
    'format': 'bestaudio/best',  # 形式を限定せず最適なものを選ぶ
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',
        'preferredquality': '192',
    }],
    'outtmpl': 'temp_audio',
    'quiet': True,
    # 切り出し時間を指定する引数を、よりエラーの出にくい形式に変更
    'external_downloader_args': ['-ss', '0', '-t', str(sec), '-loglevel', 'error']
}
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # AI解析（マスターデータ作成）
                segments, _ = model.transcribe("temp_audio.wav", word_timestamps=True, language="en")
                st.session_state.master_data = [
                    {"word": w.word.strip(), "start": w.start, "end": w.end, "dur": w.end - w.start} 
                    for s in segments for w in s.words
                ]
                
                # 音声のBase64化
                with open("temp_audio.wav", "rb") as f:
                    st.session_state.audio_b64 = base64.b64encode(f.read()).decode()
                
                st.session_state.last_url = url
                
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

    # --- 4. ビジュアルガイドUI ---
    if 'master_data' in st.session_state:
        st.subheader("Visual Guide & Practice")
        
        subtitle_html = "".join([
            f'<span id="w{i}" style="font-size:24px; font-weight:bold; display:inline-block; padding:2px 5px; color:white; transition:0.1s;">{m["word"]}</span> ' 
            for i, m in enumerate(st.session_state.master_data)
        ])

        st.components.v1.html(f"""
            <div style="background:#111; padding:30px; border-radius:15px; text-align:center; font-family:sans-serif; color:white;">
                <div id="status" style="color:#00f2fe; font-weight:bold; margin-bottom:15px;">Ready</div>
                <div id="scriptArea" style="background:#1a1a1a; padding:20px; border-radius:10px; line-height:2.5;">
                    {subtitle_html}
                </div>
                <audio id="player" src="data:audio/wav;base64,{st.session_state.audio_b64}"></audio>
                <div style="margin-top:20px;">
                    <button onclick="playDemo()" style="padding:15px 30px; border-radius:30px; cursor:pointer; background:#27ae60; color:white; border:none; font-weight:bold;">🔁 Listen & Guide</button>
                </div>
            </div>

            <script>
                const audio = document.getElementById('player');
                const masterData = {st.session_state.master_data};
                
                function playDemo() {{
                    audio.currentTime = 0;
                    audio.play();
                    draw();
                }}

                function draw() {{
                    const ct = audio.currentTime;
                    masterData.forEach((m, i) => {{
                        const el = document.getElementById('w' + i);
                        if (!el) return;
                        
                        // 0.75秒前の水色予兆
                        if (ct >= m.start - 0.75 && ct < m.start) {{
                            el.style.color = "#00f2fe";
                            el.style.transform = "scale(1.0)";
                        }} 
                        // 再生中ハイライト
                        else if (ct >= m.start && ct <= m.end) {{
                            el.style.color = "#f1c40f";
                            el.style.transform = "scale(1.2)";
                        }} 
                        // 通過済みまたは待機
                        else {{
                            el.style.color = ct > m.end ? "#666" : "white";
                            el.style.transform = "scale(1.0)";
                        }}
                    }});
                    if (!audio.paused) requestAnimationFrame(draw);
                }}
            </script>
        """, height=450)

        # --- 5. 判定セクション ---
        st.divider()
        st.info("練習が完了したら、ここに録音ファイルをアップロードして採点（開発中）")
