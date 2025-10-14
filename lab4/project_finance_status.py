import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'company_data.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS project_finance_status (
        project_id INTEGER PRIMARY KEY,
        project_name TEXT NOT NULL,
        budget REAL NOT NULL,
        spent REAL NOT NULL,
        utilization_percent REAL NOT NULL,
        status TEXT NOT NULL
    )
''')

cursor.execute('SELECT project_id, project_name, budget, spent FROM Projects')
projects = cursor.fetchall()

status_data = []
for project in projects:
    project_id, project_name, budget, spent = project
    
    if budget == 0:
        utilization_percent = 0.0
    else:
        utilization_percent = (spent / budget) * 100
    
    status = "Рисковые" if utilization_percent > 90 else "Стабильные"
    
    status_data.append((
        project_id,
        project_name,
        budget,
        spent,
        round(utilization_percent, 2),
        status
    ))

cursor.execute('DELETE FROM project_finance_status')

cursor.executemany('''
    INSERT OR REPLACE INTO project_finance_status
    (project_id, project_name, budget, spent, utilization_percent, status)
    VALUES (?, ?, ?, ?, ?, ?)
''', status_data)

conn.commit()
conn.close()

print("Таблица project_finance_status успешно обновлена.")
