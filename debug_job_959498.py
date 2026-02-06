import sqlite3
import json

try:
    conn = sqlite3.connect('new_video_compare/backend/new_video_compare.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Using external_job_id or searching by id if it matches
    # User said "959498", looking for likelihood of it being a job name or ID substring
    cursor.execute("SELECT * FROM comparison_jobs WHERE job_name LIKE '%959498%' OR id=959498 LIMIT 1")
    job = cursor.fetchone()
    
    if job:
        print(f"Job ID: {job['id']}")
        print(f"Name: {job['job_name']}")
        print(f"Comparison Status: {job['status']}")
        
        # Get comparison results
        cursor.execute("SELECT * FROM comparison_results WHERE job_id = ?", (job['id'],))
        result = cursor.fetchone()
        
        if result:
            print(f"Overall Similarity: {result['overall_similarity']}")
            print(f"Is Match: {result['is_match']}")
            
            report = json.loads(result['report_data']) if result['report_data'] else {}
            
            if 'ocr' in report:
                print("\nOCR Data:")
                print(f"Text Similarity: {report['ocr'].get('text_similarity')}")
                print(f"Differences Found: {report['ocr'].get('has_differences')}")
                print("Differences List:", report['ocr'].get('differences'))
                print("Timeline Sample:", report['ocr'].get('timeline')[:2] if report['ocr'].get('timeline') else "None")
            else:
                print("\nNo OCR report data found.")
                
            if 'video' in report:
                 print("\nVideo Diff Frames:", list(report['video']['diff_frames'].keys()) if 'diff_frames' in report['video'] else "None")

    else:
        print("Job 959498 not found")

except Exception as e:
    print(f"Error: {e}")
finally:
    if conn:
        conn.close()
