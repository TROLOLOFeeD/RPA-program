import os
import re
from googleapiclient.discovery import build
from generate_invoice import generate_invoice

def process_requests(drive, sheets_service, rpa_folder_id):
    """
    Основная функция: находит заявки и обрабатывает их
    Возвращает True, если всё прошло успешно, иначе False
    """

    def find_subfolder_by_name(parent_id, name):
        safe_name = name.replace("'", "\\'")
        query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents"
        results = drive.files().list(q=query, fields="files(id, name)", supportsAllDrives=True).execute()
        folders = results.get('files', [])
        if len(folders) != 1:
            raise Exception(f"Ожидалась 1 папка '{name}' внутри папки ID={parent_id}, найдено: {len(folders)}")
        return folders[0]['id']

    try:
        requests_folder_id = find_subfolder_by_name(rpa_folder_id, 'Заявки')
        print(f"✅ Папка Заявки найдена (ID: {requests_folder_id})")
    except Exception as e:
        print(f"❌ Не найдена папка Заявок: {e}")
        return False

    # Ищем заявки
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

    if not requests:
        print("🕗 Нет новых заявок.")
        return True

    for req in requests:
        try:
            # ... (вся логика обработки одной заявки: чтение, валидация, генерация)
            # (скопируй целиком тело цикла из bot_read.py)
            sheet_id = req['id']
            file_name = req['name']
            sender_warehouse = file_name.split('-')[1]

            range_name = 'Лист1!A1:E30'
            sheet_data = sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            values = sheet_data.get('values', [])

            if not values or len(values) < 6:
                print(f"⚠️ Заявка {file_name} слишком короткая — пропускаем")
                continue

            def get_value_from_cell(vals, row_idx, col_idx=1):
                if len(vals) > row_idx and len(vals[row_idx]) > col_idx:
                    return vals[row_idx][col_idx].strip()
                return ""

            try:
                date_val = get_value_from_cell(values, 0, 1)
                receiver_warehouse = get_value_from_cell(values, 1, 1)
                receiver_fio = get_value_from_cell(values, 2, 1)
            except Exception as e:
                print(f"❌ Ошибка при извлечении метаданных: {e}")
                continue

            items = []
            for i in range(6, len(values)):
                row = values[i] if i < len(values) else []
                while len(row) < 5:
                    row.append("")
                if not any(cell.strip() for cell in row[:3]):
                    continue
                item = {
                    "num": row[0].strip(),
                    "name": row[1].strip(),
                    "qty": row[2].strip(),
                    "price": row[3].strip(),
                    "total": row[4].strip()
                }
                items.append(item)

            # === ВАЛИДАЦИЯ ===
            ALLOWED_WAREHOUSES = {"СкладА", "СкладБ", "СкладВ", "СкладГ", "СкладД"}
            errors = []

            if not date_val.strip():
                errors.append(("B1", "Дата отсутствует"))
            if sender_warehouse not in ALLOWED_WAREHOUSES:
                errors.append(("Имя файла", "Недопустимый склад отправления"))
            if not receiver_warehouse.strip() or receiver_warehouse not in ALLOWED_WAREHOUSES:
                errors.append(("B2", "Склад назначения отсутствует или некорректен"))
            if not receiver_fio.strip():
                errors.append(("B3", "Приёмщик не указан"))

            for i, item in enumerate(items):
                row_num = 7 + i
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

            if errors:
                # ... (обработка ошибок: переименование, покраска — скопируй из bot_read.py)
                print(f"❌ Ошибок: {len(errors)}")
                for cell, msg in errors:
                    print(f"   → {cell}: {msg}")

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
                            "range": {"sheetId": sheet_id_0, "startRowIndex": r, "endRowIndex": r + 1, "startColumnIndex": c, "endColumnIndex": c + 1},
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
                    rpa_folder_id=rpa_folder_id
                )
                if not pdf_path or pdf_path.startswith("drive_id:"):
                    print("✅ Успешно обработана")

                    # === НОВОЕ: переименовать заявку в "Обработано..." ===
                    try:
                        # Извлекаем дату из заявки (date_val) и склад из имени файла
                        # Формат даты: "16.10.2025" → оставляем как есть
                        # Имя файла: "Заявка 16.10.2025-СкладА" → sender_warehouse = "СкладА"

                        new_status_name = f"Обработано {date_val}-{sender_warehouse}"
                        file_meta = drive.files().get(fileId=sheet_id, fields="parents", supportsAllDrives=True).execute()
                        parents = file_meta.get("parents", [])

                        drive.files().update(
                            fileId=sheet_id,
                            body={"name": new_status_name},
                            addParents=','.join(parents) if parents else None,
                            supportsAllDrives=True
                        ).execute()
                        print(f"   → Заявка переименована в: {new_status_name}")
                    except Exception as rename_err:
                        print(f"⚠️ Не удалось переименовать заявку: {rename_err}")

                else:
                    print("❌ Ошибка генерации — будет повтор")
                    return False

        except Exception as e:
            print(f"⚠️ Ошибка при обработке заявки {req['name']}: {e}")
            return False

    return True