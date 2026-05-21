import sqlite3
import os

db_path = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/new_video_compare.db"
print("DB size:", os.path.getsize(db_path))

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", cursor.fetchall())

# Query for job 548 in comparison_jobs
cursor.execute("SELECT * FROM comparison_jobs WHERE id = 548;")
print("Job 548 in comparison_jobs:", cursor.fetchone())

# Query for recent jobs
cursor.execute("SELECT id, status, created_at FROM comparison_jobs ORDER BY id DESC LIMIT 5;")
print("Recent comparison_jobs:")
for row in cursor.fetchall():
    print(row)

conn.close()
