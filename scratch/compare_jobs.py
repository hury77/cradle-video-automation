
import sqlite3
import json

db_path = "/Users/hubert.rycaj/Documents/cradle-video-automation/new_video_compare/backend/new_video_compare.db"

def compare_jobs(job_id_1, job_id_2):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for job_id in [job_id_1, job_id_2]:
        print(f"\n======================================")
        print(f"         ANALYZING JOB {job_id}")
        print(f"======================================")
        
        # Job info
        cursor.execute("SELECT * FROM comparison_jobs WHERE id = ?", (job_id,))
        job = cursor.fetchone()
        if not job:
            print(f"Job {job_id} not found.")
            continue
            
        print(f"Processing Time: {job['processing_duration']}s")
        
        # Results
        cursor.execute("SELECT * FROM comparison_results WHERE job_id = ?", (job_id,))
        res = cursor.fetchone()
        if res:
            print(f"Overall Sim: {res['overall_similarity']}")
            print(f"Video Sim: {res['video_similarity']}")
            print(f"Audio Sim: {res['audio_similarity']}")
            
        # Video Results
        cursor.execute("SELECT * FROM video_comparison_results WHERE job_id = ?", (job_id,))
        vid = cursor.fetchone()
        if vid:
            print(f"Frames Analyzed: {vid['total_frames']}")
            print(f"Diff Frames: {vid['different_frames']}")
            
        # QA Decision
        cursor.execute("SELECT * FROM qa_decisions WHERE job_id = ?", (job_id,))
        qa = cursor.fetchone()
        if qa:
            print(f"QA Verdict: {qa['verdict']}")
            print(f"QA Reasoning: {qa['reasoning']}")
            


    conn.close()

if __name__ == "__main__":
    compare_jobs(357, 358)
