import sqlite3
import bcrypt
from datetime import datetime, date

# ------------------------------
# 1️⃣ Connect to SQLite database (creates file if not exists)
# ------------------------------
conn = sqlite3.connect("solar_crm.db")
cur = conn.cursor()

# ------------------------------
# 2️⃣ Create Tables
# ------------------------------

# user_employees table
cur.execute("""
CREATE TABLE IF NOT EXISTS user_employees (
    agent_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")

# orders table
cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name VARCHAR(200) NOT NULL,
    customer_email VARCHAR(255),
    system_size_kw DECIMAL(10,2),
    closer_id INTEGER,
    deal_close_date DATE,
    FOREIGN KEY (closer_id) REFERENCES user_employees(agent_id)
);
""")

# payout_submitted table
cur.execute("""
CREATE TABLE IF NOT EXISTS payout_submitted (
    payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    agent_id INTEGER NOT NULL,
    amount DECIMAL(10,2),
    payment_type VARCHAR(50),
    submitted_date DATE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (agent_id) REFERENCES user_employees(agent_id)
);
""")

# orders_stage table
cur.execute("""
CREATE TABLE IF NOT EXISTS orders_stage (
    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    stage VARCHAR(100),
    comment TEXT,
    updated_by INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (updated_by) REFERENCES user_employees(agent_id)
);
""")

# ------------------------------
# 3️⃣ Insert Sample Data (with hashed passwords)
# ------------------------------

# User credentials (email → plain password)
user_credentials = {
    "alice@example.com": ("Alice Johnson", "alicepass", "Closer"),
    "bob@example.com": ("Bob Singh", "bobpass", "Setter"),
    "charlie@example.com": ("Charlie Verma", "charliepass", "Admin"),
    "deepak@example.com": ("Deepak Yadav", "deepakpass", "Closer"),
    "esha@example.com": ("Esha Mehta", "eshapass", "Setter"),
}

employees = []
for email, (name, plain_pw, role) in user_credentials.items():
    hashed_pw = bcrypt.hashpw(plain_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    employees.append((name, email, hashed_pw, role))

cur.executemany("""
INSERT INTO user_employees (name, email, password_hash, role)
VALUES (?, ?, ?, ?);
""", employees)

# Insert 5 orders
orders = [
    ("Rahul Sharma", "rahul@gmail.com", 5.5, 1, "2025-01-10"),
    ("Amit Singh", "amit@gmail.com", 6.0, 1, "2025-02-12"),
    ("Deepak Gupta", "deepak@gmail.com", 4.8, 2, "2025-03-05"),
    ("Neha Tiwari", "neha@gmail.com", 7.2, 4, "2025-04-01"),
    ("Ravi Patel", "ravi@gmail.com", 5.0, 4, "2025-05-20")
]
cur.executemany("""
INSERT INTO orders (customer_name, customer_email, system_size_kw, closer_id, deal_close_date)
VALUES (?, ?, ?, ?, ?);
""", orders)

# Insert 10 payouts
payouts = [
    (1, 1, 30000, "M1", "2025-01-15"),
    (1, 1, 20000, "M2", "2025-02-10"),
    (2, 2, 15000, "ADVANCE", "2025-02-18"),
    (3, 2, 10000, "M1", "2025-03-12"),
    (4, 4, 18000, "M1", "2025-04-05"),
    (5, 4, 12000, "M2", "2025-05-10"),
    (None, 1, 5000, "ADVANCE", "2025-06-01"),
    (None, 2, 7000, "ADVANCE", "2025-06-05"),
    (1, 3, 25000, "M1", "2025-01-20"),
    (2, 3, 18000, "M2", "2025-02-15")
]
cur.executemany("""
INSERT INTO payout_submitted (order_id, agent_id, amount, payment_type, submitted_date)
VALUES (?, ?, ?, ?, ?);
""", payouts)

# Insert 8 order stages
stages = [
    (1, "Project Acceptance", "Initial docs verified", 1),
    (1, "Engineering", "Design completed", 1),
    (2, "Permitting", "Approval pending", 2),
    (2, "Install Scheduled", "Installation planned", 2),
    (3, "Installation Complete", "Completed successfully", 4),
    (4, "Inspection", "Awaiting inspection", 4),
    (5, "PTO", "Power turned on", 4),
    (5, "Complete", "All steps done", 4)
]
cur.executemany("""
INSERT INTO orders_stage (order_id, stage, comment, updated_by)
VALUES (?, ?, ?, ?);
""", stages)

# ------------------------------
# 4️⃣ Commit and Close
# ------------------------------
conn.commit()
conn.close()

print("✅ Database created successfully with hashed passwords and sample data.")
