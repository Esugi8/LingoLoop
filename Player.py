import streamlit as st
import json
import os
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
# --- Script.py から関数をインポート ---
from Script import process_youtube_video

# --- 設定 ---
APP_NAME = "LingoLoop AI"
TOKEN_FILE = 'token.json'
DRIVE_FOLDER_ID = '1S1c7T0qe1e84xDvEZsZBQuFRbLREph1C' # Script.pyと同じもの
SCOPES = ['https://www.googleapis.com/auth/drive']

st.set_page_config(page_title=APP_NAME, layout="wide")

# --- Google Drive 連携関数 ---
# def get_drive_service():
    # creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # return build('drive', 'v3', credentials=creds)
    
def get_drive_service():
    # ファイルからではなく、Secretsの辞書から認証情報を生成
    token_info = st.secrets["google_drive_token"]
    creds = Credentials.from_authorized_user_info(token_info, SCOPES)
    return build('drive', 'v3', credentials=creds)

def list_saved_videos():
    service = get_drive_service()
    # 親フォルダ内のフォルダ（動画ID）一覧を取得 (ゴミ箱を除外)
    results = service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()
    return results.get('files', [])

def get_files_in_folder(folder_id):
    service = get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(id, name, mimeType)"
    ).execute()
    return results.get('files', [])

def download_file(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return fh.getvalue()

# --- メイン UI ---
st.title(f"🎧 {APP_NAME}")

# サイドバーの設定
with st.sidebar:
    # --- 新規動画の追加セクション ---
    st.header("新規動画を追加")
    new_url = st.text_input("YouTube URL")
    new_folder_name = st.text_input("保存名 (空なら動画ID)")
    
    if st.button("解析開始"):
        if new_url:
            with st.spinner("解析中... 数分かかります"):
                try:
                    process_youtube_video(new_url, new_folder_name)
                    st.success("解析完了！")
                    st.rerun() # リストを更新するために再起動
                except Exception as e:
                    st.error(f"解析エラー: {e}")
        else:
            st.warning("URLを入力してください")

    st.divider()

    # --- 学習ライブラリセクション ---
    st.header("学習ライブラリ")
    videos = list_saved_videos()
    if not videos:
        st.write("保存された動画がありません。")
    
    selected_video = st.selectbox("動画を選択", videos, format_func=lambda x: x['name'])

# 動画が選択されたらデータを読み込む
if selected_video:
    with st.spinner("データを読み込んでいます..."):
        folder_id = selected_video['id']
        files = get_files_in_folder(folder_id)
        
        # JSONと動画のIDを特定
        video_id = next(f['id'] for f in files if 'video' in f['mimeType'])
        json_id = next(f['id'] for f in files if 'json' in f['mimeType'])
        
        # ダウンロード（メモリ上に保持）
        video_data = download_file(video_id)
        json_data = download_file(json_id)
        
        video_base64 = base64.b64encode(video_data).decode()
        subtitles = json.loads(json_data.decode('utf-8'))

    # JavaScript用のデータ作成
    sub_data_js = []
    for i, s in enumerate(subtitles):
        # Geminiが判定した「難しい箇所」にアイコンをつける
        prefix = "⚠️ " if s.get('is_hard') else ""
        sub_data_js.append({
            "id": i, "start": s['start'], "end": s['end'],
            "text": prefix + s['text'], "translation": s['translation'],
            "note": s.get('note', '')
        })

# --- プレイヤー HTML (スマホ最適化：動画固定＋すぐ下に字幕) ---
    html_code = f"""
    <div id="app-wrapper">
        <div id="video-top-area">
            <video id="v" controls playsinline webkit-playsinline>
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            </video>
            <div class="learning-controls">
                <button class="ctrl-btn" id="btn-prev">⏮</button>
                <button class="ctrl-btn" id="btn-repeat">🔁 <span id="r-status">OFF</span></button>
                <button class="ctrl-btn" id="btn-next">⏭</button>
            </div>
            <div class="sticky-header">
                <label><input type="checkbox" id="toggle-jp" checked> 日本語訳を表示</label>
            </div>
        </div>
        
        <div id="transcript-area">
            <div id="sl"></div>
        </div>
    </div>

    <style>
        /* 全体構造 */
        body {{ margin: 0; padding: 0; background: #fff; font-family: sans-serif; overflow: hidden; }}
        #app-wrapper {{ display: flex; flex-direction: column; height: 100vh; }}

        /* 上部：動画エリア（固定） */
        #video-top-area {{
            flex-shrink: 0;
            background: #fff;
            z-index: 100;
            border-bottom: 1px solid #eee;
            padding: 5px;
        }}
        video {{ width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 4px; }}
        
        /* コントロールボタン */
        .learning-controls {{ display: flex; gap: 4px; padding: 8px 0; }}
        .ctrl-btn {{ flex: 1; padding: 12px; border: none; border-radius: 6px; background: #2196f3; color: white; font-weight: bold; font-size: 1.1em; }}
        .ctrl-btn.active {{ background: #f44336; }}
        
        /* 日本語切り替えヘッダー */
        .sticky-header {{ padding: 5px 10px; font-size: 0.9em; color: #666; background: #fafafa; border-radius: 4px; }}

        /* 下部：字幕エリア（スクロール） */
        #transcript-area {{
            flex-grow: 1;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            padding: 10px;
            background: #fdfdfd;
        }}

        /* 字幕アイテム */
        .item {{ padding: 15px; margin-bottom: 10px; border-radius: 10px; background: #fff; border: 1px solid #eee; cursor: pointer; transition: 0.2s; }}
        .item.active {{ background: #e3f2fd; border-left: 6px solid #2196f3; transform: scale(0.98); }}
        .en {{ font-weight: bold; font-size: 1.15em; line-height: 1.4; color: #222; }}
        .jp {{ font-size: 0.95em; color: #555; margin-top: 6px; }}
        .note {{ font-size: 0.85em; color: #d32f2f; margin-top: 6px; font-style: italic; border-top: 1px dashed #eee; padding-top: 5px; }}
        .hidden {{ display: none; }}

        /* PCでの表示調整 */
        @media (min-width: 600px) {{
            #app-wrapper {{ flex-direction: row; }}
            #video-top-area {{ width: 60%; height: 100vh; overflow-y: auto; }}
            #transcript-area {{ width: 40%; height: 100vh; }}
        }}
    </style>

    <script>
        const data = {json.dumps(sub_data_js)};
        const v = document.getElementById('v');
        const sl = document.getElementById('sl');
        const ts = document.getElementById('transcript-area');
        let currentIdx = 0; let isRepeat = false;

        // 字幕の生成
        data.forEach((s, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i; div.className = 'item';
            div.innerHTML = `<div class="en">${{s.text}}</div>
                             <div class="jp">${{s.translation}}</div>
                             ${{s.note ? `<div class="note">💡 ${{s.note}}</div>` : ''}}`;
            div.onclick = () => jumpTo(i);
            sl.appendChild(div);
        }});

        function jumpTo(idx) {{
            if(idx < 0 || idx >= data.length) return;
            currentIdx = idx; v.currentTime = data[idx].start; v.play();
        }}

        // コントロール
        document.getElementById('btn-prev').onclick = () => jumpTo(currentIdx - 1);
        document.getElementById('btn-next').onclick = () => jumpTo(currentIdx + 1);
        const rBtn = document.getElementById('btn-repeat');
        rBtn.onclick = () => {{
            isRepeat = !isRepeat;
            rBtn.classList.toggle('active', isRepeat);
            document.getElementById('r-status').innerText = isRepeat ? "ON" : "OFF";
        }};
        document.getElementById('toggle-jp').onchange = (e) => {{
            document.querySelectorAll('.jp').forEach(el => el.classList.toggle('hidden', !e.target.checked));
        }};

        // 再生位置に連動してスクロール
        v.addEventListener('timeupdate', () => {{
            const now = v.currentTime;
            if (isRepeat) {{
                const s = data[currentIdx];
                if (now >= s.end - 0.05 || now < s.start - 0.2) {{ v.currentTime = s.start; v.play(); }}
                return;
            }}
            data.forEach((s, i) => {{
                if (now >= s.start && now <= s.end) {{
                    if (currentIdx !== i) {{
                        document.getElementById('s-'+currentIdx).classList.remove('active');
                        currentIdx = i;
                        const el = document.getElementById('s-'+i);
                        el.classList.add('active');
                        
                        // 字幕エリア内だけをスクロールさせる
                        const itemTop = el.offsetTop;
                        ts.scrollTo({{
                            top: itemTop - 20, // 少し余白を持って上に合わせる
                            behavior: 'smooth'
                        }});
                    }}
                }}
            }});
        }});
    </script>
    """
    st.components.v1.html(html_code, height=800) # st.iframe ではなく st.components.v1.html を推奨
    st.iframe(html_code, height=900)