import os
import time
import signal
import sys
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from bot_read import process_requests

# === Настройки ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(SCRIPT_DIR, 'oauth_client_secrets.json')
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.json')
RPA_FOLDER_ID = '1zYG3lYaZRsHH_fzC_snGxYYPDJWleb4K'

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send'
]

running = True

def signal_handler(sig, frame):
    global running
    print("\n Получен сигнал остановки. Завершаем цикл...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_oauth_services():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    drive = build('drive', 'v3', credentials=creds)
    sheets = build('sheets', 'v4', credentials=creds)
    return drive, sheets

def main():
    global running
    print("Запуск RPA-монитора...")
    
    drive, sheets_service = get_oauth_services()

    # Интервалы повтора: 1 мин → 2 мин → 5 мин → 15 мин
    retry_delays = [60, 120, 300, 900]
    
    while running:
        print(f"\n Цикл запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        success = False
        retry_count = 0

        while not success and retry_count < len(retry_delays):
            try:
                success = process_requests(drive, sheets_service, RPA_FOLDER_ID)
                if success:
                    print("Цикл завершён успешно")
                    break
            except Exception as e:
                print(f"Необработанная ошибка: {e}")

            if not success and running:
                delay = retry_delays[retry_count]
                print(f"Повтор через {delay // 60} мин...")
                time.sleep(delay)
                retry_count += 1

        if not running:
            break

        # Ждём 15 минут до следующего цикла (если не было ошибок)
        if success:
            for _ in range(15 * 60):
                if not running:
                    break
                time.sleep(1)

    print("RPA-монитор остановлен.")

if __name__ == "__main__":
    main()