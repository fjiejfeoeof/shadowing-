import streamlit as st
import os
import time
import difflib
import torch
from faster_whisper import WhisperModel
import io
import base64

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

@st.cache_data
def get_master_data(file_path):
    segments, _ = model.transcribe(file_path, language="en")
    seg_list = [s for s in segments if s.start <= 15.0]
    full_text = " ".join([s.text.strip() for s in seg_list])
    return seg_list, full_text

def play_audio_autoplay(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>"""
        st.markdown(md, unsafe_allow_html=True)

# --- UI ---
st.set_page_config(page_title="Shadowing UX", layout="centered")
st.title("🎙️ Shadowing Trainer")

AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。")
else:
    selected_file = st.selectbox("練習ファイルを選択", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)
    master_segments, master_full_text = get_master_data(file_path)

    st.divider()

    # --- ステップバイステップ形式のUI ---
    st.subheader("Step 1: 録音の準備")
    
    # 録音ウィジェット
    recorded_audio = st.audio_input("マイクをオンにしてください")

    st.subheader("Step 2: 練習スタート")
    
    # 録音中（recorded_audioが空でない、または何らかの入力がある）状態を判定
    # ※audio_inputは録音完了までNoneを返しますが、操作を促すためにボタンを配置
    
    col1, col2 = st.columns([1, 2])
    with col1:
        start_btn = st.button("🔥 再生 ＆ プロンプト開始")
    with col2:
        st.caption("録音ボタンを押した直後に、左のボタンを押すと同期します。")

    prompt_area = st.empty()
    progress_bar = st.progress(0)

    if start_btn:
        play_audio_autoplay(file_path)
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > 15.0: break
            
            now_text = ""
            for s in master_segments:
                if s.start - 0.5 <= elapsed <= s.end:
                    now_text = f"### NOW: :orange[{s.text}]"
                    break
            
            with prompt_area.container():
                st.markdown(now_text if now_text else "### (Recording...)")
            
            progress_bar.progress(min(elapsed / 15.0, 1.0))
            time.sleep(0.05)
        
        st.success("終了！録音を停止して結果を待ってください。")

    if recorded_audio:
        st.divider()
        st.subheader("Step 3: 採点結果")
        with st.spinner("解析中..."):
            u_segs, _ = model.transcribe(io.BytesIO(recorded_audio.read()), language="en")
            user_text = " ".join([s.text for s in u_segs if s.start <= 15.0]).strip()
            score = int(difflib.SequenceMatcher(None, master_full_text.lower(), user_text.lower()).ratio() * 100)
            st.metric("一致率", f"{score}%")
            st.info(f"**[お手本]**: {master_full_text}")
            st.success(f"**[あなた]**: {user_text}")
