# email_notifier.py
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64

def send_failure_email(drive_service, error_details):
    try:
        # Получаем email пользователя
        user_info = drive_service.about().get(fields="user").execute()
        user_email = user_info['user']['emailAddress']

        message = MIMEMultipart()
        message['to'] = user_email
        message['subject'] = "RPA: Не удалось создать накладную после всех попыток"
        body = f"""
        RPA-робот не смог обработать заявку даже после нескольких попыток.

        Подробности:
        {error_details}

        Проверьте:
        - Доступность файла заявки
        - Корректность данных
        - Наличие интернета и доступ к Google API
        """
        message.attach(MIMEText(body, 'plain'))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        gmail_service = build('gmail', 'v1', credentials=drive_service._http.credentials)
        gmail_service.users().messages().send(userId='me', body={'raw': raw}).execute()
        print(f"Уведомление об ошибке отправлено на {user_email}")
    except Exception as e:
        print(f"Не удалось отправить email об ошибке: {e}")