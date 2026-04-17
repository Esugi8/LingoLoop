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

def process_youtube_video(url):
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

    # 2. Gemini 解析
    print(f"--- Uploading {v_id} to Gemini ---")
    video_file = client.files.upload(file=local_video)
    while video_file.state == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    print("--- Analyzing with Gemini (High Precision) ---")
    # 0.1秒単位の精度と、確実な日本語訳を指示するプロンプト
    prompt = """
    動画の英語音声を書き起こし、1〜2文ずつのセグメントに分けたJSON形式のリストを出力してください。
    
    [出力項目]
    - 'start': 開始時間。必ず総秒数に対して0.1秒単位の精度（例: 12.3）の数値で出力してください。
    - 'end': 終了時間。必ず総秒数に対して0.1秒単位の精度（例: 15.7）の数値で出力してください。
    - 'text': 元の英語音声の書き起こし。
    - 'translation': 学習に最適な、自然で正確な日本語訳。必ず日本語で出力してください。
    - 'is_hard': 日本人にとって聞き取りにくい音声変化（連結、消失、フラップT等）があれば true。
    - 'note': 'is_hard'がtrueの場合、その音声変化の理由を日本語で解説。
    
    [制約]
    - 時間の数値は文字列（"12.3"）ではなく、数値（12.3）として出力すること。
    - セグメント間に隙間がないよう、また英語の発音の始まりと終わりに正確に合わせてください。
    - 出力は純粋なJSONのみ。解説文や ```json などの装飾は一切不要。
    """
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview", # または安定していれば gemini-2.0-flash
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1, # 低めに設定して指示への忠実度を上げる
        )
    )
    
    with open(local_json, "w", encoding="utf-8") as f:
        f.write(response.text)

    # 3. Google Drive への保存
    print("--- Storing to Google Drive ---")
    try:
        v_folder_id = create_drive_folder(v_id, DRIVE_FOLDER_ID)
        upload_to_drive(local_video, v_folder_id, 'video/mp4')
        upload_to_drive(local_json, v_folder_id, 'application/json')
    except Exception as e:
        print(f"Drive Upload Error: {e}")

    # 4. クリーンアップ
    os.remove(local_video)
    os.remove(local_json)
    client.files.delete(name=video_file.name)
    print(f"--- ALL DONE for {v_id} ---")

if __name__ == "__main__":
    test_url = "https://www.youtube.com/watch?v=z0PJnc8BFTk"
    process_youtube_video(test_url)