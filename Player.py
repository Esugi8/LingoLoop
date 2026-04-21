import streamlit as st
import json
import os
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from datetime import datetime # 追加
# --- Script.py から関数をインポート ---
from Script import process_youtube_video

# --- 設定 ---
APP_NAME = "LingoLoop AI"
TOKEN_FILE = 'token.json'
DRIVE_FOLDER_ID = '1S1c7T0qe1e84xDvEZsZBQuFRbLREph1C' # Script.pyと同じもの
SCOPES = ['https://www.googleapis.com/auth/drive',
'https://www.googleapis.com/auth/spreadsheets'
]

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
    
# スプレッドシート保存関数
def save_to_spreadsheet(en, jp, video_name, memo):
    try:
        service = get_google_service('sheets', 'v4')
        spreadsheet_id = st.secrets["SPREADSHEET_ID"]
        range_name = 'LingoLoop_Phrases!A2' # 「シート1」は実際のシート名に合わせてください
        
        values = [[en, jp, video_name, memo, datetime.now().strftime("%Y-%m-%d %H:%M")]]
        body = {'values': values}
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        return True
    except Exception as e:
        st.error(f"スプレッドシート保存エラー: {e}")
        return False

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
# タイトル (st.title) は削除

# Streamlit自体の余白を消すための魔法のCSS
# st.markdown("""
    # <style>
        # /* メインコンテンツのパディングをゼロにする */
        # .block-container {
            # padding-top: 0rem;
            # padding-bottom: 0rem;
            # padding-left: 0rem;
            # padding-right: 0rem;
        # }
        # /* ヘッダー（右上のメニューなど）を隠す */
        # header {visibility: hidden;}
        # /* フッターを隠す */
        # footer {visibility: hidden;}
    # </style>
    # """, unsafe_allow_html=True)

# サイドバーの設定
with st.sidebar:
    st.header("LingoLoop AI") # サイドバーに名前を移動
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
    
        # 単語帳登録セクション
    st.subheader("📓 単語帳に保存")
    with st.form("word_form", clear_on_submit=True):
        new_en = st.text_input("英語表現")
        new_jp = st.text_input("日本語訳")
        new_memo = st.text_area("メモ (任意)", height=60)
        submit = st.form_submit_button("スプレッドシートに保存")
        
        if submit:
            if new_en and new_jp:
                v_name = selected_video['name'] if selected_video else "Unknown"
                if save_to_spreadsheet(new_en, new_jp, v_name, new_memo):
                    st.success("保存しました！")
            else:
                st.warning("英語と日本語の両方を入力してください")

    # --- 学習ライブラリセクション ---
    st.header("学習ライブラリ")
    videos = list_saved_videos()
    if not videos:
        st.write("保存された動画がありません。")
    
    selected_video = st.selectbox("動画を選択", videos, format_func=lambda x: x['name'])

# (上部の import や関数定義は維持)

# --- 動画が選択された時の処理 ---
if selected_video:
    with st.spinner("データを読み込んでいます..."):
        folder_id = selected_video['id']
        files = get_files_in_folder(folder_id)
        
        video_id = next(f['id'] for f in files if 'video' in f['mimeType'])
        json_id = next(f['id'] for f in files if 'json' in f['mimeType'])
        
        video_data = download_file(video_id)
        json_data = download_file(json_id)
        
        video_base64 = base64.b64encode(video_data).decode()
        subtitles = json.loads(json_data.decode('utf-8'))

    # JS用データ作成 (if の中)
    sub_data_js = []
    for i, s in enumerate(subtitles):
        prefix = "⚠️ " if s.get('is_hard') else ""
        sub_data_js.append({
            "id": i, "start": s['start'], "end": s['end'],
            "text": prefix + s['text'], "translation": s['translation'],
            "note": s.get('note', '')
        })

    # --- プレイヤー HTML (ここも if の中に入れる必要があります) ---
    # 波括弧 { } はすべて {{ }} に二重化しています
    html_code = f"""
    <div id="app-wrapper">
        <div id="video-header">
            <video id="v" controls playsinline webkit-playsinline>
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            </video>
            <div class="learning-controls">
                <button class="ctrl-btn" id="btn-prev">⏮</button>
                <button class="ctrl-btn" id="btn-repeat">🔁 <span id="r-status">OFF</span></button>
                <button class="ctrl-btn" id="btn-next">⏭</button>
            </div>
            <div class="jp-toggle-bar">
                <label><input type="checkbox" id="toggle-jp" checked> 日本語訳を表示</label>
            </div>
        </div>
        
        <div id="transcript-container">
            <div id="sl"></div>
            <div style="height: 100vh;"></div>
        </div>
    </div>

    <style>
        body, html {{ 
            margin: 0; padding: 0; height: 100vh; width: 100vw;
            overflow: hidden; font-family: sans-serif; background: #fff;
        }}
        #app-wrapper {{ display: flex; flex-direction: column; height: 100vh; width: 100vw; }}
        #video-header {{ flex-shrink: 0; background: #000; z-index: 1000; }}
        video {{ width: 100%; aspect-ratio: 16/9; display: block; }}
        .learning-controls {{ display: flex; gap: 2px; padding: 4px; background: #333; }}
        .ctrl-btn {{ flex: 1; padding: 15px; border: none; border-radius: 4px; background: #555; color: white; font-weight: bold; font-size: 1.2em; }}
        .ctrl-btn.active {{ background: #f44336; }}
        .jp-toggle-bar {{ padding: 8px 12px; font-size: 0.8em; color: #ccc; background: #222; border-bottom: 1px solid #444; }}

        #transcript-container {{
            flex-grow: 1;
            overflow-y: scroll;
            background: #fff;
            -webkit-overflow-scrolling: touch;
            padding: 0 !important;
            margin: 0 !important;
            scroll-behavior: auto !important; 
        }}

        .item {{ 
            padding: 12px 15px; 
            border-bottom: 1px solid #eee; 
            cursor: pointer;
            box-sizing: border-box;
            opacity: 0.3;
            transition: opacity 0.3s, background 0.3s;
            user-select: text;
            -webkit-user-select: text;
        }}
        .item.active {{ background: #fff9c4 !important; border-left: 8px solid #2196f3; opacity: 1; }}
        .item.near {{ opacity: 0.8; }}
        .en {{ font-weight: bold; font-size: 0.85em; line-height: 1.4; color: #000; }}
        .jp {{ font-size: 0.75em; color: #555; margin-top: 4px; }}
        .note {{ font-size: 0.7em; color: #d32f2f; margin-top: 3px; }}
        .hidden {{ display: none !important; }}

        @media (min-width: 600px) {{
            #app-wrapper {{ flex-direction: row; }}
            #video-header {{ width: 70%; height: 100vh; }}
            #transcript-container {{ width: 30%; height: 100vh; }}
        }}
    </style>

    <script>
        const data = {json.dumps(sub_data_js)};
        const v = document.getElementById('v');
        const sl = document.getElementById('sl');
        const ts = document.getElementById('transcript-container');
        let currentIdx = -1; 
        let isRepeat = false;

        data.forEach((s, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i; 
            div.className = 'item';
            div.innerHTML = `<div class="en">${{s.text}}</div>
                             <div class="jp">${{s.translation}}</div>
                             ${{s.note ? `<div class="note">💡 ${{s.note}}</div>` : ''}}`;
            div.onclick = () => jumpTo(i);
            sl.appendChild(div);
        }});

        function updateScroll(idx) {{
            if (idx < 0) return;
            const items = document.querySelectorAll('.item');
            items.forEach((item, i) => {{
                item.classList.remove('active', 'near');
                if (i === idx) item.classList.add('active');
                else if (i === idx - 1 || i === idx + 1 || i === idx + 2) {{
                    item.classList.add('near');
                }}
            }});

            if (idx === 0) {{
                ts.scrollTop = 0;
            }} else {{
                const prevEl = document.getElementById('s-'+(idx-1));
                if (prevEl) {{
                    ts.scrollTop = prevEl.offsetTop;
                }}
            }}
        }}

        function jumpTo(idx) {{
            if(idx < 0 || idx >= data.length) return;
            currentIdx = idx;
            v.currentTime = data[idx].start;
            v.play();
            updateScroll(idx);
        }}

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

        v.addEventListener('timeupdate', () => {{
            const now = v.currentTime;
            if (isRepeat && currentIdx !== -1) {{
                const s = data[currentIdx];
                if (now >= s.end - 0.05 || now < s.start - 0.1) {{
                    v.currentTime = s.start;
                    v.play();
                }}
                return;
            }}
            for (let i = 0; i < data.length; i++) {{
                if (now >= data[i].start && now < data[i].end) {{
                    if (currentIdx !== i) {{
                        currentIdx = i;
                        updateScroll(i);
                    }}
                    break;
                }}
            }}
        }});
        updateScroll(0);
    </script>
    """
    # インデントに注意（if selected_video の中に入れています）
    st.iframe(html_code, height=1200)