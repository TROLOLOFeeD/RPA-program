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

    counter_path = os.path.join(os.path.dirname(__file__), 'счётчик.txt')

    if not os.path.exists(counter_path):
        with open(counter_path, 'w', encoding='utf-8') as f:
            f.write("0")
        print(f"🆕 Файл счётчика создан: {counter_path}")

    try:
        with open(counter_path, 'r', encoding='utf-8') as f:
            current_num = int(f.read().strip())
            new_num = current_num + 1
    except Exception as e:
        print(f"❌ Ошибка чтения счётчика: {e}")
        return None

    # --- Создание накладной ---
    template_path = os.path.join(os.path.dirname(__file__), 'Шаблоны', 'Шаблон_накладной.docx')
    if not os.path.exists(template_path):
        print("❌ Шаблон накладной не найден")
        return None

    doc = Document(template_path)

    # Замена меток во всём документе
    def replace_text_in_doc(doc, old, new):
        for paragraph in doc.paragraphs:
            if old in paragraph.text:
                paragraph.text = paragraph.text.replace(old, new)
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

    table = doc.tables[0]

    while len(table.rows) < 2:
        table.add_row()

    first_row = table.rows[1]
    first_row.cells[0].text = items[0]["num"]
    first_row.cells[1].text = items[0]["name"]
    first_row.cells[2].text = items[0]["qty"]
    first_row.cells[3].text = items[0]["price"]
    first_row.cells[4].text = items[0]["total"]

    for item in items[1:]:
        new_row = table.add_row()
    
        new_row.cells[0].text = item["num"]
        new_row.cells[1].text = item["name"]
        new_row.cells[2].text = item["qty"]
        new_row.cells[3].text = item["price"]
        new_row.cells[4].text = item["total"]
    
        source_cells = first_row.cells
        target_cells = new_row.cells
    
        for i in range(min(len(source_cells), len(target_cells))):
            src_cell = source_cells[i]
            tgt_cell = target_cells[i]
        
            if src_cell.paragraphs and tgt_cell.paragraphs:
                src_para = src_cell.paragraphs[0]
                tgt_para = tgt_cell.paragraphs[0]
            
                tgt_para.alignment = src_para.alignment
            
                pf = tgt_para.paragraph_format
                spf = src_para.paragraph_format
                pf.left_indent = spf.left_indent
                pf.right_indent = spf.right_indent
                pf.first_line_indent = spf.first_line_indent
                pf.space_before = spf.space_before
                pf.space_after = spf.space_after
                pf.line_spacing = spf.line_spacing
                pf.line_spacing_rule = spf.line_spacing_rule
            
                if src_para.style:
                    tgt_para.style = src_para.style

    temp_docx_path = os.path.join(os.path.dirname(__file__), f'Накладная_{new_num}.docx')
    doc.save(temp_docx_path)

    try:
        from docx2pdf import convert
        pdf_path = temp_docx_path.replace('.docx', '.pdf')
        convert(temp_docx_path, pdf_path)
        os.remove(temp_docx_path)
    except ImportError:
        print("Модуль docx2pdf не установлен — используем загрузку в Drive")
        return None

    pdf_name = f"Накладная {date_val}-{new_num}_{sender_warehouse}-{receiver_warehouse}.pdf"
    pdf_final_path = os.path.join(os.path.dirname(__file__), 'Накладные', pdf_name)

    os.makedirs(os.path.dirname(pdf_final_path), exist_ok=True)
    os.rename(pdf_path, pdf_final_path)

    with open(counter_path, 'w', encoding='utf-8') as f:
        f.write(str(new_num))

    print(f"Накладная сгенерирована: {pdf_name}")

    # --- Загрузка в Google Drive ---
    def find_subfolder_by_name(drive_service, parent_id, name):
        safe_name = name.replace("'", "\\'")
        query = f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True
        ).execute()
        folders = results.get('files', [])
        if len(folders) != 1:
            raise Exception(f"Ожидалась 1 папка '{name}' в родителе '{parent_id}', найдено: {len(folders)}")
        return folders[0]['id']

    from googleapiclient.http import MediaFileUpload

    try:
        invoices_folder_id = find_subfolder_by_name(drive_service, rpa_folder_id, 'Накладные')
    
        file_metadata = {
            'name': pdf_name,
            'parents': [invoices_folder_id],
            'mimeType': 'application/pdf'
        }

        media = MediaFileUpload(pdf_final_path, mimetype='application/pdf')

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()

        print(f"☁️ PDF загружен в Google Drive (ID: {uploaded_file.get('id')})")

        try:
            user_info = drive_service.about().get(fields="user").execute()
            user_email = user_info['user']['emailAddress']

            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import base64

            message = MIMEMultipart()
            message['to'] = user_email
            message['subject'] = f"✅ Накладная создана: {pdf_name}"
            body = f"""
            Успешно создана и загружена накладная.

            Дата: {date_val}
            Склад отправления: {sender_warehouse}
            Склад назначения: {receiver_warehouse}
            Приёмщик: {receiver_fio}
            Позиций: {len(items)}

            Номер накладной: {new_num}
            ID файла в Google Drive: {uploaded_file.get('id')}
            """
            message.attach(MIMEText(body, 'plain'))

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            gmail_service = build('gmail', 'v1', credentials=drive_service._http.credentials)
            gmail_service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()

            print(f"Уведомление отправлено на {user_email}")

        except Exception as e:
            print(f"Не удалось отправить email: {e}")

        return f"drive_id:{uploaded_file.get('id')}"
    
    except Exception as e:
        print(f"Ошибка загрузки в Google Drive: {e}")
        return pdf_final_path