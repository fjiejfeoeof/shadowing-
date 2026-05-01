import streamlit as st
import os
import difflib
import torch
from faster_whisper import WhisperModel
from pydub import AudioSegment  # 音声カット用に追加

# --- 1. AIモデルの準備 ---
@st.cache_resource
def load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 音声解析 & トリミング関数 ---
def process_audio(file_path, duration_sec):
    # 音声の読み込みとカット
    audio = AudioSegment.from_file(file_path)
    # duration_sec（秒）をミリ秒に変換して切り出し
    trimmed_audio = audio[:duration_sec * 1000]
    
    temp_trimmed_path = "trimmed_sample.wav"
    trimmed_audio.export(temp_trimmed_path, format="wav")
    
    # 切り出した音声を解析
    segments, _ = model.transcribe(temp_trimmed_path, language="en")
    text = " ".join([segment.text for segment in segments])
    return text.strip(), temp_trimmed_path

# --- 3. アプリケーション設定 ---
st.set_page_config(page_title="Standard Shadowing App", layout="centered")
st.title("🎙️ Shadowing Practice (Stable Edition)")

AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。")
else:
    # 設定エリア
    st.sidebar.header("Settings")
    # 追加：練習秒数の指定
    practice_sec = st.sidebar.slider("練習する秒数", min_value=5, max_value=60, value=15, step=5)
    
    selected_file = st.selectbox("練習するファイルを選択してください", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    st.divider()

    # 4. お手本の解析と再生
    st.subheader(f"1. お手本を聴く ({practice_sec}秒間)")
    
    with st.spinner("AIが指定範囲を解析中..."):
        # 指定秒数でお手本テキストと音声ファイルを生成
        master_text, master_audio_path = process_audio(file_path, practice_sec)
    
    # カットした音声を再生
    with open(master_audio_path, "rb") as f:
        st.audio(f.read(), format="audio/wav")

    with st.expander("お手本のスクリプトを表示"):
        st.write(master_text)

    st.divider()

    # 5. ユーザーの録音アップロード
    st.subheader("2. Shadowing & Upload")
    st.info(f"上の音声を聴いてシャドーイングし、{practice_sec}秒程度の録音ファイルをアップロードしてください。")
    user_audio = st.file_uploader("録音ファイルをドロップ", type=["mp3", "wav", "m4a"])

    if user_audio:
        with st.spinner("あなたの声を解析中..."):
            with open("user_temp.wav", "wb") as f:
                f.write(user_audio.getbuffer())
            
            user_segments, _ = model.transcribe("user_temp.wav", language="en")
            user_text = " ".join([s.text for s in user_segments]).strip()
            
            st.write(f"**あなたの発話:** {user_text}")

            ratio = difflib.SequenceMatcher(None, master_text.lower(), user_text.lower()).ratio()
            score = int(ratio * 100)

            st.subheader("3. Result")
            st.metric(label="一致率", value=f"{score}%")
