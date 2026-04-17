import os
import time
import json
import yt_dlp
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv("API.env")

# --- 設定項目 ---
TOKEN_FILE = 'token.json'
DRIVE_FOLDER_ID = '1S1c7T0qe1e84xDvEZsZBQuFRbLREph1C' 
SCOPES = ['https://www.googleapis.com/auth/drive']

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_drive_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(local_path, drive_folder_id, mime_type):
    service = get_drive_service()
    file_metadata = {'name': os.path.basename(local_path), 'parents': [drive_folder_id]}
    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def create_drive_folder(folder_name, parent_id):
    service = get_drive_service()
    file_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    file = service.files().create(body=file_metadata, fields='id').execute()
    return file.get('id')

# --- Script.py の該当箇所を修正 ---

# 関数の引数に custom_folder_name を追加
def process_youtube_video(url, custom_folder_name=None):
    local_video = "temp_video.mp4"
    local_json = "temp_subtitles.json"

    # 1. YouTubeダウンロード
    ydl_opts = {
        'format': 'mp4[height<=480]',
        'outtmpl': local_video,
        'nocheckcertificate': True,
        'overwrites': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        v_id = info['id']
        # フォルダ名の決定：指定があればそれを使用、なければ動画ID
        folder_display_name = custom_folder_name if custom_folder_name else v_id

    # 2. Gemini 解析
    print(f"--- Uploading {v_id} to Gemini ---")
    video_file = client.files.upload(file=local_video)
    while video_file.state == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    print("--- Analyzing with Gemini (High Precision) ---")
    prompt = """
    動画の英語音声を書き起こし、1〜2文ずつのセグメントに分けたJSON形式のリストを出力してください。
    
    [出力項目]
    - 'start': 開始時間(数値、0.1秒単位)
    - 'end': 終了時間(数値、0.1秒単位)
    - 'text': 元の英語書き起こし
    - 'translation': 日本語訳
    - 'is_hard': 音声変化で聞き取りにくい箇所なら true
    - 'note': 音声変化の理由(日本語)
    """
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
    )
    
    with open(local_json, "w", encoding="utf-8") as f:
        f.write(response.text)

    # 3. Google Drive への保存
    print("--- Storing to Google Drive ---")
    try:
        # フォルダ作成時に folder_display_name を使用
        v_folder_id = create_drive_folder(folder_display_name, DRIVE_FOLDER_ID)
        upload_to_drive(local_video, v_folder_id, 'video/mp4')
        upload_to_drive(local_json, v_folder_id, 'application/json')
    except Exception as e:
        print(f"Drive Upload Error: {e}")

    # 4. クリーンアップ
    os.remove(local_video)
    os.remove(local_json)
    client.files.delete(name=video_file.name)
    print(f"--- ALL DONE for {folder_display_name} ---")

if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=z0PJnc8BFTk"
    process_youtube_video(test_url)