# generate_invoice.py

import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from docx import Document
from docx.shared import Pt
from datetime import datetime

from docx.shared import Inches

def generate_invoice(
    sheet_id,
    file_name,
    sender_warehouse,
    receiver_warehouse,
    receiver_fio,
    date_val,
    items,
    drive_service,
    sheets_service,
    rpa_folder_id
):
    """
    Генерирует накладную в формате PDF
    Возвращает путь к PDF или None при ошибке
    """

    # --- 1. Получить номер накладной ---
    counter_path = os.path.join(os.path.dirname(__file__), 'счётчик.txt')

    # Если файла нет — создаём с начальным значением
    if not os.path.exists(counter_path):
        with open(counter_path, 'w', encoding='utf-8') as f:
            f.write("0")  # или "0", если хочешь начать с 1
        print(f"🆕 Файл счётчика создан: {counter_path}")

    try:
        with open(counter_path, 'r', encoding='utf-8') as f:
            current_num = int(f.read().strip())
            new_num = current_num + 1
    except Exception as e:
        print(f"❌ Ошибка чтения счётчика: {e}")
        return None

    # --- 2. Заполнить шаблон Word ---
    template_path = os.path.join(os.path.dirname(__file__), 'Шаблоны', 'Шаблон_накладной.docx')
    if not os.path.exists(template_path):
        print("❌ Шаблон накладной не найден")
        return None

    doc = Document(template_path)

    # Замена меток во всём документе — в параграфах и таблицах
    def replace_text_in_doc(doc, old, new):
        # Параграфы
        for paragraph in doc.paragraphs:
            if old in paragraph.text:
                paragraph.text = paragraph.text.replace(old, new)
        # Таблицы
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if old in cell.text:
                        cell.text = cell.text.replace(old, new)

    replace_text_in_doc(doc, "{{date}}", date_val)
    replace_text_in_doc(doc, "{{number}}", str(new_num))
    replace_text_in_doc(doc, "{{sender_warehouse}}", sender_warehouse)
    replace_text_in_doc(doc, "{{receiver_warehouse}}", receiver_warehouse)
    replace_text_in_doc(doc, "{{receiver_fio}}", receiver_fio)

    # Заполнение таблицы — начинаем со второй строки (индекс 1)
    table = doc.tables[0]

    # Убедимся, что есть минимум 2 строки (заголовки + данные)
    while len(table.rows) < 2:
        table.add_row()

    # Первую строку данных заполняем напрямую
    first_row = table.rows[1]
    first_row.cells[0].text = items[0]["num"]
    first_row.cells[1].text = items[0]["name"]
    first_row.cells[2].text = items[0]["qty"]
    first_row.cells[3].text = items[0]["price"]
    first_row.cells[4].text = items[0]["total"]

    # Если есть дополнительные позиции — добавляем их
    for item in items[1:]:
        # Добавляем новую строку
        new_row = table.add_row()
    
        # Заполняем текст
        new_row.cells[0].text = item["num"]
        new_row.cells[1].text = item["name"]
        new_row.cells[2].text = item["qty"]
        new_row.cells[3].text = item["price"]
        new_row.cells[4].text = item["total"]
    
        # === КОПИРУЕМ ФОРМАТИРОВАНИЕ ИЗ ПЕРВОЙ СТРОКИ ДАННЫХ ===
        source_cells = first_row.cells
        target_cells = new_row.cells
    
        for i in range(min(len(source_cells), len(target_cells))):
            src_cell = source_cells[i]
            tgt_cell = target_cells[i]
        
            # Копируем форматирование параграфа (все ключевые параметры)
            if src_cell.paragraphs and tgt_cell.paragraphs:
                src_para = src_cell.paragraphs[0]
                tgt_para = tgt_cell.paragraphs[0]
            
                # Копируем выравнивание
                tgt_para.alignment = src_para.alignment
            
                # Копируем отступы
                pf = tgt_para.paragraph_format
                spf = src_para.paragraph_format
                pf.left_indent = spf.left_indent
                pf.right_indent = spf.right_indent
                pf.first_line_indent = spf.first_line_indent
                pf.space_before = spf.space_before
                pf.space_after = spf.space_after
                pf.line_spacing = spf.line_spacing
                pf.line_spacing_rule = spf.line_spacing_rule
            
                # Копируем стиль (если есть)
                if src_para.style:
                    tgt_para.style = src_para.style

        # === ОПЦИОНАЛЬНО: копируем границы ячеек (если они есть) ===
        # В Word границы таблицы обычно применяются ко всей таблице,
        # поэтому если первая строка имеет границы — новые строки их унаследуют автоматически.
        # Если нет — см. примечание ниже.

    # Сохранить временный DOCX
    temp_docx_path = os.path.join(os.path.dirname(__file__), f'Накладная_{new_num}.docx')
    doc.save(temp_docx_path)

    # --- 3. Экспорт в PDF ---
    # Используем Google Drive API для конвертации (если нет docx2pdf)
    # Или можно использовать docx2pdf — но требует установки

    # Альтернатива: загрузить DOCX в Drive → экспортировать в PDF → скачать
    # Но проще — если у тебя есть возможность — установи `pip install docx2pdf`

    try:
        from docx2pdf import convert
        pdf_path = temp_docx_path.replace('.docx', '.pdf')
        convert(temp_docx_path, pdf_path)
        os.remove(temp_docx_path)  # удаляем временный DOCX
    except ImportError:
        print("⚠️ Модуль docx2pdf не установлен — используем загрузку в Drive")
        # Здесь можно реализовать загрузку DOCX в Drive и экспорт через API
        # Пока пропустим — если нужна детализация — скажи.
        return None

    # --- 4. Переименовать PDF и сохранить в папку "Накладные" ---
    pdf_name = f"Накладная {date_val}-{new_num}_{sender_warehouse}-{receiver_warehouse}.pdf"
    pdf_final_path = os.path.join(os.path.dirname(__file__), 'Накладные', pdf_name)

    # Убедимся, что папка существует
    os.makedirs(os.path.dirname(pdf_final_path), exist_ok=True)
    os.rename(pdf_path, pdf_final_path)

    # --- 5. Обновить счётчик ---
    with open(counter_path, 'w', encoding='utf-8') as f:
        f.write(str(new_num))

    print(f"✅ Накладная сгенерирована: {pdf_name}")

    # --- 6. Загрузка в Google Drive ---
    def find_subfolder_by_name(drive_service, parent_id, name):
        safe_name = name.replace("'", "\\'")
        query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True  # ← Добавлено!
        ).execute()
        folders = results.get('files', [])
        if len(folders) != 1:
            raise Exception(f"Ожидалась 1 папка '{name}' в родителе '{parent_id}', найдено: {len(folders)}")
        return folders[0]['id']

    from googleapiclient.http import MediaFileUpload

    try:
        # Найти папку "Накладные" внутри RPA
        invoices_folder_id = find_subfolder_by_name(drive_service, rpa_folder_id, 'Накладные')
    
        file_metadata = {
            'name': pdf_name,
            'parents': [invoices_folder_id],
            'mimeType': 'application/pdf'
        }

        media = MediaFileUpload(pdf_final_path, mimetype='application/pdf')

        # Загрузка с поддержкой всех дисков (включая "Мой диск")
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True  # ← ВАЖНО!
        ).execute()

        print(f"☁️ PDF загружен в Google Drive (ID: {uploaded_file.get('id')})")

        return f"drive_id:{uploaded_file.get('id')}"

    except Exception as e:
        print(f"❌ Ошибка загрузки в Google Drive: {e}")
        return pdf_final_path