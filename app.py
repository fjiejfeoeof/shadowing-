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

# --- 2. 解析ロジック ---
@st.cache_data
def get_master_data(file_path):
    segments, _ = model.transcribe(file_path, language="en")
    seg_list = [s for s in segments if s.start <= 15.0]
    full_text = " ".join([s.text.strip() for s in seg_list])
    return seg_list, full_text

# 自動再生用の関数（HTMLを直接書かず、Base64で音声を埋め込む安全な方法）
def play_audio_autoplay(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        # autoplay属性をつけた隠しオーディオタグを生成
        md = f"""
            <audio autoplay="true">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)

# --- 3. メインUI ---
st.set_page_config(page_title="One-Click Shadowing", layout="centered")
st.title("🎙️ One-Click Shadowing Prompter")

AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。")
else:
    selected_file = st.selectbox("練習するファイルを選択:", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    with st.spinner("AIが準備中..."):
        master_segments, master_full_text = get_master_data(file_path)

    st.divider()

    # --- プロンプター連動再生 ---
    st.subheader("1. 練習スタート")
    st.write("下のボタンを押すと、音声が流れ、プロンプターが開始します。")
    
    prompt_area = st.empty()
    progress_bar = st.progress(0)
    
    # 【ここが重要】ボタン一つですべてを完結させる
    if st.button("🔥 再生 ＆ プロンプター起動"):
        # 1. 音声を自動再生（隠しタグを出す）
        play_audio_autoplay(file_path)
        
        # 2. 即座にプロンプターのループを開始
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > 15.0: break
            
            now_text = ""
            next_text = ""
            
            for i, s in enumerate(master_segments):
                if s.start - 0.5 <= elapsed <= s.end:
                    now_text = f"### NOW: :orange[{s.text}]"
                    if i + 1 < len(master_segments):
                        next_text = f"Next: {master_segments[i+1].text}"
                    break
            
            with prompt_area.container():
                st.markdown(now_text if now_text else "### (Ready...)")
                if next_text:
                    st.caption(next_text)
            
            progress_bar.progress(min(elapsed / 15.0, 1.0))
            time.sleep(0.05)
        
        st.success("15秒の練習が終了しました！")

    st.divider()

    # --- 録音・採点セクション ---
    st.subheader("2. 自分の声を録音して比較")
    recorded_audio = st.audio_input("録音ボタンを押して発音を確認")

    if recorded_audio:
        with st.spinner("採点中..."):
            u_segs, _ = model.transcribe(io.BytesIO(recorded_audio.read()), language="en")
            user_text = " ".join([s.text for s in u_segs if s.start <= 15.0]).strip()
            
            ratio = difflib.SequenceMatcher(None, master_full_text.lower(), user_text.lower()).ratio()
            score = int(ratio * 100)
            
            st.metric("一致率", f"{score}%")
            
            col1, col2 = st.columns(2)
            with col1: st.info(f"**[お手本]**\n{master_full_text}")
            with col2: st.success(f"**[あなた]**\n{user_text if user_text else '???'}")
