# Dodaj ten endpoint do api/v1/compare.py

@router.get("/jobs", response_model=List[ComparisonJob])
async def get_jobs(db: Session = Depends(get_db)):
    """Get all comparison jobs"""
    jobs = db.query(models.ComparisonJob).order_by(models.ComparisonJob.created_at.desc()).all()
    return jobs
