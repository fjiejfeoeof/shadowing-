import streamlit as st
import os
import time
import difflib
import torch
from faster_whisper import WhisperModel
import io

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 解析ロジック（エラー回避版：セグメント単位） ---
@st.cache_data
def get_master_data(file_path):
    # word_timestampsを使わず、標準的なsegmentsのみを使用
    segments, _ = model.transcribe(file_path, language="en")
    
    display_data = []
    full_text_list = []
    
    for segment in segments:
        if segment.start > 15.0:
            break
        # セグメント（一塊の文章）単位でリスト化
        display_data.append({
            "text": segment.text.strip(),
            "start": segment.start,
            "end": segment.end
        })
        full_text_list.append(segment.text.strip())
    
    return display_data, " ".join(full_text_list)

# 差分表示用の関数（前回と同じ）
def get_diff_markdown(master, user):
    m_words = master.lower().replace('.', '').replace(',', '').split()
    u_words = user.lower().replace('.', '').replace(',', '').split()
    user_set = set(u_words)
    result = [word if word in user_set else f"~~:red[{word}]~~" for word in m_words]
    return " ".join(result)

# --- 3. メインUI ---
st.set_page_config(page_title="Shadowing Prompter Fixed", layout="centered")
st.title("🎙️ Shadowing Prompter (Fixed Edition)")

AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。")
else:
    selected_file = st.selectbox("練習するファイルを選択:", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    with st.spinner("AIがスクリプトを準備中..."):
        master_segments, master_full_text = get_master_data(file_path)

    st.divider()

    # --- プロンプター機能 ---
    st.subheader("1. プロンプター連動再生")
    
    # プレースホルダーの設置
    prompt_area = st.empty()
    progress_bar = st.progress(0)
    
    st.audio(file_path)
    
    if st.button("プロンプターをスタート"):
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > 15.0: break
            
            current_phrase = ""
            next_phrase = ""
            
            for i, s in enumerate(master_segments):
                # 0.5秒前に次のフレーズを表示するロジック
                if s.start - 0.5 <= elapsed <= s.end:
                    current_phrase = f"### NOW: :orange[{s.text}]"
                    if i + 1 < len(master_segments):
                        next_phrase = f"Next: {master_segments[i+1]['text']}"
                    break
            
            # 表示更新
            # current_phraseがない（無音区間など）場合は前の表示をクリア
            with prompt_area.container():
                st.markdown(current_phrase if current_phrase else "### (Listening...)")
                if next_phrase:
                    st.caption(next_phrase)
            
            progress_bar.progress(min(elapsed / 15.0, 1.0))
            time.sleep(0.1)
        
        st.success("終了！下のマイクで録音してください。")

    st.divider()

    # --- 録音・採点（前回と同様） ---
    st.subheader("2. Shadowing & Result")
    recorded_audio = st.audio_input("録音を開始")

    if recorded_audio:
        with st.spinner("採点中..."):
            u_segments, _ = model.transcribe(io.BytesIO(recorded_audio.read()), language="en")
            user_text = " ".join([s.text for s in u_segments if s.start <= 15.0]).strip()
            
            score = int(difflib.SequenceMatcher(None, master_full_text.lower(), user_text.lower()).ratio() * 100)
            
            st.metric("一致率", f"{score}%")
            st.markdown(f"**フィードバック:**\n> {get_diff_markdown(master_full_text, user_text)}")
            
            col1, col2 = st.columns(2)
            with col1: st.info(f"**[お手本]**\n{master_full_text}")
            with col2: st.success(f"**[あなた]**\n{user_text if user_text else '???'}")
