import os
import sqlite3
import random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'company_data.db')

project_names = [
    "Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta",
    "Iota", "Kappa", "Lambda", "Mu", "Nu", "Xi", "Omicron", "Pi", "Rho",
    "Sigma", "Tau", "Upsilon", "Phi", "Chi", "Psi", "Omega",
    "Nebula", "Horizon", "Pioneer", "Vanguard", "Apex", "Summit",
    "Fusion", "Quantum", "Orion", "Aurora", "Catalyst", "Nexus",
    "Infinity", "Zenith", "Eclipse", "Pulse", "Vertex", "Stratos",
    "Helix", "Nova", "Terra", "Aether", "Vortex", "Quasar", "Echo",
    "Spectrum", "Cipher", "Onyx", "Obsidian", "Phantom", "Raven",
    "Stellar", "Comet", "Galaxy", "Meteor", "Solaris", "Lunar",
    "Astra", "Cosmos", "Draco", "Lyra", "Orionis", "Polaris",
    "Sirius", "Vega", "Altair", "Capella", "Rigel", "Betelgeuse",
    "Antares", "Deneb", "Spica", "Regulus", "Aldebaran", "Pollux",
    "Castor", "Procyon", "Arcturus", "Canopus", "Fomalhaut", "Vindemiatrix"
]

managers = [
    "Иван Петров", "Мария Сидорова", "Алексей Иванов", "Елена Кузнецова",
    "Дмитрий Смирнов", "Анна Попова", "Сергей Васильев", "Ольга Морозова",
    "Артём Новиков", "Татьяна Лебедева", "Максим Соколов", "Наталья Юрьева",
    "Павел Зайцев", "Юлия Фролова", "Роман Гусев", "Ксения Волкова",
    "Владимир Белов", "Анастасия Орлова", "Григорий Фёдоров", "Виктория Швецова"
]

records = []
start_date = datetime(2025, 1, 1)
end_date = datetime(2027, 12, 31)

for i in range(1, 101):
    project_name = f"{random.choice(project_names)}_{i}"
    manager = random.choice(managers)
    budget = random.randint(50000, 2000000)
    spent = random.randint(0, budget)
    deadline = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
    deadline_str = deadline.strftime('%Y-%m-%d')
    
    records.append((i, project_name, manager, budget, spent, deadline_str))

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS Projects (
        project_id INTEGER PRIMARY KEY,
        project_name TEXT NOT NULL,
        manager TEXT NOT NULL,
        budget INTEGER NOT NULL,
        spent INTEGER NOT NULL,
        deadline TEXT NOT NULL
    )
''')

cursor.executemany('''
    INSERT INTO Projects (project_id, project_name, manager, budget, spent, deadline)
    VALUES (?, ?, ?, ?, ?, ?)
''', records)

conn.commit()
conn.close()
