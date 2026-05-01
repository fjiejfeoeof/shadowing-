import streamlit as st
import os
from faster_whisper import WhisperModel
import difflib

# --- 1. 準備：モデルとサンプル設定 ---
@st.cache_resource
def load_model():
    return WhisperModel("base", device="cpu", compute_type="int8") # 安定のCPU

model = load_model()

# サンプルデータ（本来はjson等で管理するが、まずはコード内に直書き）
SAMPLES = {
    "Sample 1: Basic Greeting": {
        "audio": "samples/sample1.mp3",
        "text": "Hello, how are you doing today? It is a beautiful morning."
    },
    "Sample 2: Tech News": {
        "audio": "samples/sample2.mp3",
        "text": "Artificial intelligence is changing the way we work and live in the future."
    },
    "Sample 3: Daily Life": {
        "audio": "samples/sample3.mp3",
        "text": "I would like to order a cup of coffee and a piece of chocolate cake please."
    }
}

# --- 2. 画面構成（HTML一切なし） ---
st.title("🎙️ Shadowing Alpha: 堅実版")
st.write("URL弾かれもボタン消失もありません。確実に練習しましょう。")

# 1. お手本を選ぶ
selected_label = st.selectbox("練習する素材を選んでください", list(SAMPLES.keys()))
sample = SAMPLES[selected_label]

# 2. お手本を聴く
st.subheader("1. Listen")
if os.path.exists(sample["audio"]):
    st.audio(sample["audio"])
else:
    st.error(f"ファイル {sample['audio']} が見つかりません。フォルダを確認してください。")

# 3. 字幕を確認
with st.expander("お手本のスクリプトを表示"):
    st.write(sample["text"])

# 4. 録音ファイルをアップロード
st.subheader("2. Shadowing & Upload")
st.info("スマホやPCの録音アプリで録った声を、下のボタンからアップロードしてください。")
user_voice = st.file_uploader("録音ファイルをドロップ", type=["wav", "mp3", "m4a"])

# 5. 採点実行
if user_voice:
    with st.spinner("AI採点中..."):
        # 一時保存
        with open("user_temp.wav", "wb") as f:
            f.write(user_voice.getbuffer())
        
        # Whisperで文字起こし
        segments, _ = model.transcribe("user_temp.wav")
        user_text = "".join([s.text for s in segments]).strip()
        
        # 比較
        score = difflib.SequenceMatcher(None, sample["text"].lower(), user_text.lower()).ratio()
        
        # 結果表示
        st.subheader("3. Result")
        st.metric(label="シャドーイング一致率", value=f"{int(score * 100)}%")
        
        col1, col2 = st.columns(2)
        with col1:
            st.caption("お手本")
            st.write(sample["text"])
        with col2:
            st.caption("あなたの声（AI認識結果）")
            st.write(user_text)
