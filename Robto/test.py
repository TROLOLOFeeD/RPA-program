import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Путь к папке, где лежит САМ СКРИПТ
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')

print(f"Using: {CREDENTIALS_PATH}")
if not os.path.exists(CREDENTIALS_PATH):
    raise FileNotFoundError(f"File credentials.json not found: {CREDENTIALS_PATH}")

creds = service_account.Credentials.from_service_account_file(
    CREDENTIALS_PATH,
    scopes=[
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets'
    ]
)
drive = build('drive', 'v3', credentials=creds)
files = drive.files().list(pageSize=5).execute()
print("Files аre available:", len(files.get('files', [])) > 0)
for f in files.get('files', []):
    print(f"Files found: {f['name']} (ID: {f['id']})")