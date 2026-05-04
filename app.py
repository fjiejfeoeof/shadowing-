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
    # Streamlit Cloud環境を考慮し、CPUでも動くint8量子化モデルを使用
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return WhisperModel("base", device=device, compute_type="int8")

model = load_model()

# --- 2. 解析ロジック ---
@st.cache_data
def get_master_data(file_path):
    """
    お手本音声を解析し、単語ごとのタイミング情報を取得する
    """
    segments, _ = model.transcribe(file_path, word_timestamps=True, language="en")
    words_data = []
    full_text = ""
    for segment in segments:
        full_text += segment.text + " "
        for word in segment.words:
            # 15秒制限
            if word.start > 15.0:
                break
            words_data.append({"word": word.word.strip(), "start": word.start, "end": word.end})
    return words_data, full_text.strip()

def get_diff_markdown(master_text, user_text):
    """
    マークダウン記法のみで差分を視覚化する
    """
    m_words = master_text.lower().replace('.', '').replace(',', '').split()
    u_words = user_text.lower().replace('.', '').replace(',', '').split()
    
    result = []
    user_set = set(u_words)
    
    for word in m_words:
        if word in user_set:
            result.append(word)
        else:
            # 言えなかった単語を赤文字＋打ち消し線（Streamlit標準記法）
            result.append(f"~~:red[{word}]~~")
    return " ".join(result)

# --- 3. メインUI ---
st.set_page_config(page_title="Standard Prompter Studio", layout="centered")
st.title("🎙️ Shadowing Prompter Studio")

# ファイル選択
AUDIO_DIR = "."
audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.m4a'))]

if not audio_files:
    st.error("音声ファイルが見つかりません。リポジトリに配置してください。")
else:
    selected_file = st.selectbox("練習するファイルを選択:", audio_files)
    file_path = os.path.join(AUDIO_DIR, selected_file)

    # データ準備
    with st.spinner("AIがプロンプトを生成中..."):
        master_words, master_full_text = get_master_data(file_path)

    st.divider()

    # --- プロンプター機能 ---
    st.subheader("1. プロンプター連動再生")
    st.info("再生ボタンを押すと、プロンプターが動き出します。")
    
    # プロンプター表示用のプレースホルダー
    current_word_placeholder = st.empty()
    next_word_placeholder = st.empty()
    progress_bar = st.progress(0)
    
    # 音声プレイヤー
    st.audio(file_path)
    
    # 再生と同期するためのトリガー
    if st.button("プロンプターをスタート"):
        start_time = time.time()
        total_duration = 15.0 # 練習制限時間
        
        # 0.1秒刻みで画面を更新するループ（Python制御）
        while True:
            elapsed = time.time() - start_time
            if elapsed > total_duration:
                break
            
            # 現在の単語と「0.5秒先」の予見単語を探す
            current_w = ""
            next_w = ""
            
            for i, w in enumerate(master_words):
                # 約0.5秒前に予見表示するための判定
                if w.start - 0.5 <= elapsed <= w.end:
                    current_w = f"### NOW: :orange[{w.word}]"
                    if i + 1 < len(master_words):
                        next_w = f"Next: {master_words[i+1]['word']}"
                    break
            
            # 画面更新
            current_word_placeholder.markdown(current_w if current_w else "### ---")
            next_word_placeholder.text(next_w if next_w else "")
            
            # プログレスバー更新（視覚的ガイド）
            progress_bar.progress(min(elapsed / total_duration, 1.0))
            
            time.sleep(0.05) # CPU負荷を抑えつつ滑らかに更新
        
        st.success("再生終了")

    st.divider()

    # --- 録音・採点機能 ---
    st.subheader("2. あなたのシャドーイング")
    recorded_audio = st.audio_input("録音を開始（最大15秒）")

    if recorded_audio:
        with st.spinner("AI採点中..."):
            # ユーザー音声解析
            u_segments, _ = model.transcribe(io.BytesIO(recorded_audio.read()), language="en")
            user_text = " ".join([s.text for s in u_segments if s.start <= 15.0]).strip()
            
            # 採点
            score = int(difflib.SequenceMatcher(None, master_full_text.lower(), user_text.lower()).ratio() * 100)
            
            st.metric("一致率", f"{score}%")

            # 視覚的フィードバック（上下比較）
            st.write("### 視覚的フィードバック")
            
            # 差分ハイライト
            diff_md = get_diff_markdown(master_full_text, user_text)
            st.markdown(f"> {diff_md}")
            st.caption("赤色＋打ち消し線：聞き取り不明、または飛ばした箇所")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**[お手本]**")
                st.info(master_full_text)
            with col2:
                st.markdown("**[あなたの発話]**")
                st.success(user_text if user_text else "音が聞き取れませんでした")
