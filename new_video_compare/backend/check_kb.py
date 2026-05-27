from models.database import SessionLocal
from models.models import ComparisonJob as ComparisonJobModel, QADecision

def check_kb():
    with SessionLocal() as db:
        total_jobs = db.query(ComparisonJobModel).count()
        completed_jobs = db.query(ComparisonJobModel).filter(ComparisonJobModel.status == "COMPLETED").count()
        total_decisions = db.query(QADecision).count()
        
        print("\n--- STATYSTYKI BAZY WIEDZY ---")
        print(f"Liczba wszystkich zadań (Jobs) w bazie: {total_jobs}")
        print(f"Liczba zakończonych zadań (status COMPLETED): {completed_jobs}")
        print(f"Liczba wpisów w bazie wiedzy (QADecision): {total_decisions}")
        
        if total_decisions > 0:
            print("\nOstatnie wpisy w KB:")
            decisions = db.query(QADecision).order_by(QADecision.created_at.desc()).limit(5).all()
            for d in decisions:
                print(f"- Job ID {d.job_id}: Werdykt={d.verdict}, Klient={d.client_name}, Powód={d.reasoning[:60]}...")

if __name__ == "__main__":
    check_kb()
