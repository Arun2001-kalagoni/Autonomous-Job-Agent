import sqlite3
import chromadb
import os

# 1. Define Paths (Ensuring they exist)
DATA_DIR = "data"
SQL_DB_PATH = os.path.join(DATA_DIR, "jobs.db")
CHROMA_PATH = os.path.join(DATA_DIR, "career_memory")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def init_tracking_db():
    """Initializes the SQLite DB to track application status."""
    conn = sqlite3.connect(SQL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            job_title TEXT,
            link TEXT UNIQUE,
            status TEXT, 
            match_score INTEGER,
            date_applied TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ SQL Tracking Database Initialized at:", SQL_DB_PATH)

def log_application(company, job_title, link, status, match_score):
    """Logs evaluation or application status to SQLite database."""
    conn = sqlite3.connect(SQL_DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO applications (company, job_title, link, status, match_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (company, job_title, link, status, match_score))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already exists (Unique link)
    finally:
        conn.close()

def get_chroma_collection():
    """Initializes and returns the ChromaDB collection for RAG."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # We name the collection 'career_history'
    collection = client.get_or_create_collection(name="career_history")
    print("✅ ChromaDB Career Memory Initialized at:", CHROMA_PATH)
    return collection

if __name__ == "__main__":
    # Run this file directly to set up your infrastructure
    init_tracking_db()
    get_chroma_collection()