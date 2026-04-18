# --- 3. URL入力後の処理 (31行目付近から) ---
    if url:
        # 音声取得処理
        if 'audio_b64' not in st.session_state or st.session_state.get('last_url') != url:
            with st.spinner("音声を生成・解析中..."):
                try:
                    # yt-dlp設定
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'wav',
                            'preferredquality': '192',
                        }],
                        'outtmpl': 'temp_audio',
                        'quiet': True,
                        'external_downloader_args': ['-ss', '0', '-t', str(sec), '-loglevel', 'error']
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
