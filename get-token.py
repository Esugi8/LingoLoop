# get_token.py
from google_auth_oauthlib.flow import InstalledAppFlow
import json

# 前回のコードと同じスコープ
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def main():
    # PCにある credentials.json を読み込む
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # 認証情報を辞書形式で出力
    token_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    print("\n--- 下記の内容をコピーして Streamlit Secrets に貼り付けてください ---\n")
    print(json.dumps(token_dict, indent=2))

if __name__ == '__main__':
    main()