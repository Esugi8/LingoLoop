import streamlit as st
import json
import os

# --- 設定 ---
VIDEO_PATH = "sample_video.mp4"
JSON_PATH = "subtitles.json"

st.set_page_config(page_title="Learning Player Check", layout="wide")

st.title("📖 英語学習プレイヤー機能チェック")

def timestamp_to_seconds(ts):
    """'0:03' や '1:20' などの形式を秒数(float)に変換する。既に数値ならそのまま返す。"""
    if isinstance(ts, (int, float)):
        return float(ts)
    
    if isinstance(ts, str):
        # '00:03' or '0:03' or '1:02:03' などの形式に対応
        parts = ts.split(':')
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    
    return float(ts) # それ以外は型変換を試みる

# ファイル存在確認
if not os.path.exists(VIDEO_PATH) or not os.path.exists(JSON_PATH):
    st.error("ファイルが見つかりません。")
    st.stop()

with open(JSON_PATH, "r", encoding="utf-8") as f:
    subtitles = json.load(f)

# 再生開始位置を保持
if 'start_time' not in st.session_state:
    st.session_state.start_time = 0.0

col_vid, col_txt = st.columns([3, 2])

with col_vid:
    st.subheader("Video Player")
    # st.video は秒数(int or float)を期待する
    st.video(VIDEO_PATH, start_time=int(st.session_state.start_time))
    st.write(f"現在のシーク位置: {st.session_state.start_time} 秒")

with col_txt:
    st.subheader("Segments")
    show_translation = st.toggle("和訳を表示する", value=True)

    container = st.container(height=600)
    with container:
        for i, item in enumerate(subtitles):
            with st.container(border=True):
                st.write(f"**{item['text']}**")
                if show_translation:
                    st.caption(item['translation'])
                
                # ここで変換関数を適用
                try:
                    start_sec = timestamp_to_seconds(item['start'])
                except:
                    start_sec = 0.0

                if st.button(f"▶ Play at {item['start']}", key=f"btn_{i}"):
                    st.session_state.start_time = start_sec
                    st.rerun()