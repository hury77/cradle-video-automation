import sqlite3
import os
import sys

db_path = "new_video_compare/backend/new_video_compare.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get job 524
cursor.execute("SELECT * FROM comparison_jobs WHERE id = 524")
job = cursor.fetchone()
if not job:
    print("Job 524 not found!")
    sys.exit(1)

# Print columns
colnames = [d[0] for d in cursor.description]
job_dict = dict(zip(colnames, job))
print("Job 524 Details:")
for k, v in job_dict.items():
    if k not in ['report_data', 'video_result', 'audio_result']:
        print(f"  {k}: {v}")

# Check files
acceptance_file_id = job_dict['acceptance_file_id']
emission_file_id = job_dict['emission_file_id']

print(f"\nAcceptance File ID: {acceptance_file_id}")
cursor.execute("SELECT * FROM files WHERE id = ?", (acceptance_file_id,))
acc_file = cursor.fetchone()
if acc_file:
    acc_colnames = [d[0] for d in cursor.description]
    acc_dict = dict(zip(acc_colnames, acc_file))
    print("Acceptance File Details:")
    for k, v in acc_dict.items():
        print(f"  {k}: {v}")
    print(f"  Exists on disk: {os.path.exists(acc_dict['file_path'])}")
else:
    print("Acceptance file not found in DB!")

print(f"\nEmission File ID: {emission_file_id}")
cursor.execute("SELECT * FROM files WHERE id = ?", (emission_file_id,))
emi_file = cursor.fetchone()
if emi_file:
    emi_colnames = [d[0] for d in cursor.description]
    emi_dict = dict(zip(emi_colnames, emi_file))
    print("Emission File Details:")
    for k, v in emi_dict.items():
        print(f"  {k}: {v}")
    print(f"  Exists on disk: {os.path.exists(emi_dict['file_path'])}")
else:
    print("Emission file not found in DB!")
