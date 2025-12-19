import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from generate_invoice import generate_invoice

# === OAuth 2.0 настройки ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(SCRIPT_DIR, 'oauth_client_secrets.json')  # ← новый файл
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.json')  # ← создаётся автоматически

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_oauth_services():
    creds = None
    # Загружаем токен, если он есть
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # Если токена нет или он просрочен — обновляем
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            # Запускает браузер для входа
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        # Сохраняем токен для будущих запусков
        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    
    # Возвращаем оба сервиса
    drive_service = build('drive', 'v3', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    return drive_service, sheets_service

# === Получаем авторизованные сервисы ===
drive, sheets_service = get_oauth_services()

# ID папки RPA (остаётся прежним)
RPA_FOLDER_ID = '1zYG3lYaZRsHH_fzC_snGxYYPDJWleb4K'

# === Найти папку "Заявки" внутри RPA (теперь точно по ID родителя) ===
def find_subfolder_by_name(parent_id, name):
    safe_name = name.replace("'", "\\'")
    query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents"
    results = drive.files().list(q=query, fields="files(id, name)", supportsAllDrives=True).execute()
    folders = results.get('files', [])
    if len(folders) != 1:
        raise Exception(f"Ожидалась 1 папка '{name}' внутри папки ID={parent_id}, найдено: {len(folders)}")
    return folders[0]['id']

# Получаем ID папки "Заявки"
requests_folder_id = find_subfolder_by_name(RPA_FOLDER_ID, 'Заявки')
print(f"✅ Папка Заявки найдена (ID: {requests_folder_id})")

# Ищем заявки внутри "Заявки"
query = (
    f"name contains 'Заявка ' "
    f"and '{requests_folder_id}' in parents "
    f"and mimeType = 'application/vnd.google-apps.spreadsheet'"
)
result = drive.files().list(q=query, fields="files(id, name)", supportsAllDrives=True).execute()
requests = result.get('files', [])

print(f"📄 Найдено заявок: {len(requests)}")
for req in requests:
    print(f"  - {req['name']} (ID: {req['id']})")
    

for req in requests:
    sheet_id = req['id']
    file_name = req['name']  # Пример: "Заявка 16.10.2025-СкладА"

    # --- 1. Извлекаем склад отправления из имени ---
    sender_warehouse = file_name.split('-')[1]  # "СкладА"

    # --- 2. Читаем данные с листа 'Лист1' ---
    range_name = 'Лист1!A1:E30'  # Достаточно для заголовков + 20 строк
    sheet_data = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_name
    ).execute()

    values = sheet_data.get('values', [])

    if not values or len(values) < 6:
        print(f"⚠️ Заявка {file_name} слишком короткая — пропускаем")
        continue

    # --- 3. Парсим ключевые поля ---

    def get_value_from_cell(values, row_idx, col_idx=1):
        """Читает значение из указанной строки и колонки (по умолчанию - B)"""
        if len(values) > row_idx and len(values[row_idx]) > col_idx:
            return values[row_idx][col_idx].strip()
        return ""

    try:
        date_val = get_value_from_cell(values, 0, 1)          # B1: Дата
        receiver_warehouse = get_value_from_cell(values, 1, 1)  # B2: Склад назначения
        receiver_fio = get_value_from_cell(values, 2, 1)       # B3: Приёмщик
    except Exception as e:
        print(f"❌ Ошибка при извлечении метаданных: {e}")
        continue

    print(f"📄 Заявка: {file_name}")
    print(f"   Дата: {date_val}")
    print(f"   Склад отправления: {sender_warehouse}")
    print(f"   Склад назначения: {receiver_warehouse}")
    print(f"   Приёмщик: {receiver_fio}")

    # --- 4. Извлекаем таблицу позиций ---
    items = []
    start_row = 6  # Данные начинаются со СТРОКИ 7 → индекс 7 (0-based)
    for i in range(start_row, len(values)):
        row = values[i] if i < len(values) else []
    
        # Гарантируем, что в строке минимум 5 ячеек
        while len(row) < 5:
            row.append("")
    
        # Пропускаем полностью пустые строки
        if not any(cell.strip() for cell in row[:3]):  # Если нет №, наименования или кол-ва
            continue

        item = {
            "num": row[0].strip(),
            "name": row[1].strip(),
            "qty": row[2].strip(),
            "price": row[3].strip(),
            "total": row[4].strip()
        }
        items.append(item)

    print(f"   Позиций: {len(items)}")
    for item in items[:3]:
        print(f"     → {item['num']}. {item['name']} — {item['qty']} шт., цена: {item['price']}, сумма: {item['total']}")

    # === ВАЛИДАЦИЯ ===
    ALLOWED_WAREHOUSES = {"СкладА", "СкладБ", "СкладВ", "СкладГ", "СкладД"}

    errors = []

    # 1. Проверка метаданных
    if not date_val.strip():
        errors.append(("B1", "Дата отсутствует"))
    if sender_warehouse not in ALLOWED_WAREHOUSES:
        errors.append(("Имя файла", "Недопустимый склад отправления"))
    if not receiver_warehouse.strip() or receiver_warehouse not in ALLOWED_WAREHOUSES:
        errors.append(("B2", "Склад назначения отсутствует или некорректен"))
    if not receiver_fio.strip():
        errors.append(("B3", "Приёмщик не указан"))

    # 2. Проверка позиций
    for i, item in enumerate(items):
        row_idx = 6 + i  # данные начинаются со строки 8 в Google Sheets → индекс 7 в массиве = строка 8
        row_num = row_idx + 1  # номер строки в Google Sheets (1-based)

        if not item["num"].strip():
            errors.append((f"A{row_num}", "Пустой № п/п"))
        if not item["name"].strip():
            errors.append((f"B{row_num}", "Пустое наименование"))
        if not item["qty"].strip() or not item["qty"].isdigit() or int(item["qty"]) <= 0:
            errors.append((f"C{row_num}", "Кол-во должно быть целым числом > 0"))
        if not item["price"].strip() or not item["price"].replace('.', '').isdigit():
            errors.append((f"D{row_num}", "Цена должна быть числом"))
        if not item["total"].strip():
            errors.append((f"E{row_num}", "Сумма отсутствует"))

    # === ВАЛИДАЦИЯ (вставить ПОСЛЕ чтения items) ===
    ALLOWED_WAREHOUSES = {"СкладА", "СкладБ", "СкладВ", "СкладГ", "СкладД"}

    errors = []

    # Проверка метаданных
    if not date_val.strip():
        errors.append(("B1", "Дата отсутствует"))
    if sender_warehouse not in ALLOWED_WAREHOUSES:
        errors.append(("Имя файла", "Недопустимый склад отправления"))
    if not receiver_warehouse.strip() or receiver_warehouse not in ALLOWED_WAREHOUSES:
        errors.append(("B2", "Склад назначения отсутствует или некорректен"))
    if not receiver_fio.strip():
        errors.append(("B3", "Приёмщик не указан"))

    # Проверка позиций
    for i, item in enumerate(items):
        row_num = 6 + i + 1  
        if not item["num"].strip():
            errors.append((f"A{row_num}", "Пустой №"))
        if not item["name"].strip():
            errors.append((f"B{row_num}", "Пустое наименование"))
        if not item["qty"].strip() or not item["qty"].isdigit() or int(item["qty"]) <= 0:
            errors.append((f"C{row_num}", "Кол-во: число > 0"))
        if not item["price"].strip() or not item["price"].replace('.', '').isdigit():
            errors.append((f"D{row_num}", "Цена: число"))
        if not item["total"].strip():
            errors.append((f"E{row_num}", "Сумма отсутствует"))

    # === ОБРАБОТКА ===
    if errors:
        print(f"❌ Ошибок: {len(errors)}")
        for cell, msg in errors:
            print(f"   → {cell}: {msg}")

        # --- Переименование ---
        file_meta = drive.files().get(fileId=sheet_id, fields="parents", supportsAllDrives=True).execute()
        parents = file_meta.get("parents", [])
        new_name = req['name'].replace("Заявка", "Ошибка", 1)
        drive.files().update(
            fileId=sheet_id,
            body={"name": new_name},
            addParents=','.join(parents) if parents else None,
            supportsAllDrives=True
        ).execute()
        print(f"   → Переименована в: {new_name}")

        # --- Покраска ---
        sheet_meta = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheet_id_0 = sheet_meta['sheets'][0]['properties']['sheetId']
        RED_BG = {"red": 234/255, "green": 67/255, "blue": 53/255}

        def a1_to_rc(a1):
            import re
            m = re.match(r"([A-Z]+)(\d+)", a1.upper())
            if not m: return None, None
            col_s, row_s = m.groups()
            row = int(row_s) - 1
            col = sum((ord(c) - 64) * (26 ** i) for i, c in enumerate(reversed(col_s))) - 1
            return row, col

        paint_requests = []
        for cell, _ in errors:
            if cell == "Имя файла": continue
            r, c = a1_to_rc(cell)
            if r is None: continue
            paint_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id_0,
                        "startRowIndex": r,
                        "endRowIndex": r + 1,
                        "startColumnIndex": c,
                        "endColumnIndex": c + 1
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": RED_BG}},
                    "fields": "userEnteredFormat.backgroundColor"
                }
            })

        if paint_requests:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": paint_requests}
            ).execute()
            print("   → Ячейки закрашены (#ea4335)")

    else:
        print("✅ Заявка прошла валидацию — начинаем генерацию накладной")

        # Передаём все данные в функцию генерации
        pdf_path = generate_invoice(
            sheet_id=sheet_id,
            file_name=file_name,
            sender_warehouse=sender_warehouse,
            receiver_warehouse=receiver_warehouse,
            receiver_fio=receiver_fio,
            date_val=date_val,
            items=items,
            drive_service=drive,
            sheets_service=sheets_service,
            rpa_folder_id=RPA_FOLDER_ID
        )

        if pdf_path:
            print(f"🎉 Накладная сохранена: {pdf_path}")
        else:
            print("❌ Ошибка при генерации накладной")