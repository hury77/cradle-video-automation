import sqlite3
import json

db_path = "new_video_compare.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get the last 10 files
cursor.execute("""
    SELECT id, filename, original_name, is_processed, processing_error, codec, file_metadata, created_at 
    FROM files 
    ORDER BY id DESC 
    LIMIT 10
""")

rows = cursor.fetchall()
print("--- LAST 10 FILES IN DATABASE ---")
for row in rows:
    f_id, fname, orig, processed, error, codec, meta, created = row
    print(f"ID: {f_id}")
    print(f"  Filename: {fname}")
    print(f"  Original: {orig}")
    print(f"  Processed: {processed}")
    print(f"  Error: {error}")
    print(f"  Codec: {codec}")
    print(f"  Metadata: {meta}")
    print(f"  Created: {created}")
    print("-" * 40)

conn.close()
