import sqlite3
import sys

try:
    conn = sqlite3.connect('new_video_compare/backend/new_video_compare.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, progress, updated_at FROM comparison_jobs ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"Job ID: {row[0]}, Status: {row[1]}, Progress: {row[2]}, Last Updated: {row[3]}")
    else:
        print("No jobs found")
except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        conn.close()
