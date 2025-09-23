import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
import os

CSV_FILE_PATH = "C:/Users/User/Desktop/train_labels.csv"
EMAIL = "asdqazsedc@mail.ru"
PASSWORD = "8YhJi14J1aX3PLLXutAS"
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587
IMAP_SERVER = "imap.mail.ru"
IMAP_PORT = 993
RECIPIENT = EMAIL

DOWNLOAD_FOLDER = "./downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


try:
    df = pd.read_csv(CSV_FILE_PATH, nrows=5)
    table_html = df.to_html(index=False, border=1, classes="dataframe")
except Exception as e:
    print(f"Ошибка при чтении CSV: {e}")
    exit(1)

msg = MIMEMultipart()
msg['From'] = EMAIL
msg['To'] = RECIPIENT
msg['Subject'] = "CSV данные"

html_body = f"""
<html>
  <head>
    <style>
      .dataframe {{ border-collapse: collapse; margin: 20px 0; }}
      .dataframe th, .dataframe td {{ border: 1px solid #ddd; padding: 8px; }}
      .dataframe th {{ background-color: #f2f2f2; }}
    </style>
  </head>
  <body>
    <h2>Первые строки из CSV:</h2>
    {table_html}
  </body>
</html>
"""
msg.attach(MIMEText(html_body, 'html'))

try:
    with open(CSV_FILE_PATH, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition',
        f'attachment; filename= {os.path.basename(CSV_FILE_PATH)}'
    )
    msg.attach(part)
except Exception as e:
    print(f"Ошибка при прикреплении файла: {e}")
    exit(1)

try:
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL, PASSWORD)
    server.sendmail(EMAIL, RECIPIENT, msg.as_string())
    server.quit()
    print("Письмо отправлено!")
except Exception as e:
    print(f"Ошибка при отправке: {e}")


subject_to_search = input("\n Тема письма для поиска: ").strip()

if not subject_to_search:
    print("Темы нет")
    exit()

print(f"'{subject_to_search}'...")

try:
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL, PASSWORD)
    mail.select("INBOX")

    subject_encoded = subject_to_search.encode('utf-8')
    search_criteria = f'SUBJECT "{subject_to_search}"'

    status, messages = mail.search(None, search_criteria)

    if status != 'OK':
        print("Ошибка поиска писем.")
        mail.logout()
        exit()

    email_ids = messages[0].split()
    if not email_ids:
        print("Писем не найдено.")
        mail.logout()
        exit()

    latest_email_id = email_ids[-1] 
    print(f"Найдено писем: {len(email_ids)}. Самое новое (ID: {latest_email_id.decode()}).")

    status, msg_data = mail.fetch(latest_email_id, '(RFC822)')
    if status != 'OK':
        print()
        mail.logout()
        exit()

    raw_email = msg_data[0][1]
    email_message = email.message_from_bytes(raw_email)

    attachments_found = False
    for part in email_message.walk():
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue

        filename = part.get_filename()
        if filename:
            decoded_header = email.header.decode_header(filename)[0]
            filename = decoded_header[0]
            if isinstance(filename, bytes):
                filename = filename.decode(decoded_header[1] or 'utf-8')

            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            counter = 1
            while os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                filepath = os.path.join(f"{name}_{counter}{ext}")
                counter += 1

            with open(filepath, 'wb') as f:
                f.write(part.get_payload(decode=True))
            print(f"Сохранено: {filepath}")
            attachments_found = True

    if not attachments_found:
        print("📎 Вложений в письме не найдено.")

    mail.logout()
    print("Поиск и загрузка завершены.")

except Exception as e:
    print(f"Ошибка при поиске/скачивании: {e}")
