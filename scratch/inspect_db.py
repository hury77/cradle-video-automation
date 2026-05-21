import sqlite3

conn = sqlite3.connect("/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/new_video_compare.db")
cursor = conn.cursor()

# Get the latest completed job join files
cursor.execute("""
    SELECT j.id, f_acc.original_name, f_acc.duration, f_emi.original_name, f_emi.duration
    FROM comparison_jobs j
    LEFT JOIN files f_acc ON j.acceptance_file_id = f_acc.id
    LEFT JOIN files f_emi ON j.emission_file_id = f_emi.id
    ORDER BY j.id DESC LIMIT 1
""")
row = cursor.fetchone()
if row:
    job_id, acc_name, acc_dur, emi_name, emi_dur = row
    print("JOB ID:", job_id)
    print("ACCEPTANCE NAME:", acc_name, "DURATION:", acc_dur)
    print("EMISSION NAME:", emi_name, "DURATION:", emi_dur)
else:
    print("No jobs found")

conn.close()
