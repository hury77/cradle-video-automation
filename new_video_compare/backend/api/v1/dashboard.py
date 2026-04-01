from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
import os
import csv
import io
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from models.database import get_db
from models.models import ComparisonJob, File, JobStatus, AutomationLog, QADecision, DecisionVerdict
from pydantic import BaseModel

class AutomationLogCreate(BaseModel):
    cradle_id: Optional[str] = None
    component: str
    action: str
    message: str
    is_error: bool = True
    details: Optional[Dict[str, Any]] = None

router = APIRouter(tags=["Dashboard"])

def get_dir_size(path: str) -> int:
    """Calculate total size of a directory in bytes"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get advanced dashboard statistics"""
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    
    # Base queries
    total_query = db.query(ComparisonJob)
    completed_query = total_query.filter(ComparisonJob.status == JobStatus.COMPLETED)
    
    # 1. Basic Counts
    total_jobs = total_query.count()
    completed = completed_query.count()
    failed = total_query.filter(ComparisonJob.status == JobStatus.FAILED).count()
    processing = total_query.filter(ComparisonJob.status.in_([JobStatus.PROCESSING, JobStatus.PENDING])).count()
    
    # 2. Key Performance Indicators (KPIs)
    # Success Rate
    finished_count = completed + failed
    success_rate = 0.0
    if finished_count > 0:
        success_rate = round((completed / finished_count * 100), 1)
    
    # Avg Processing Time (for completed jobs)
    avg_duration = db.query(func.avg(ComparisonJob.processing_duration)).filter(ComparisonJob.status == JobStatus.COMPLETED).scalar() or 0
    
    # Throughput (24h)
    jobs_24h = total_query.filter(ComparisonJob.created_at >= last_24h).count()
    
    # Chart Data (Last 7 Days)
    chart_data = []
    for i in range(6, -1, -1):
        day_start = now - timedelta(days=i)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        count = total_query.filter(
            ComparisonJob.created_at >= day_start,
            ComparisonJob.created_at < day_end
        ).count()
        
        chart_data.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })
    
    # 3. Client Breakdown & Formatting
    # Assuming Job Name format: "Client - Campaign - ..." or just parsing logic
    # Examples: "Electrolux_Video..." or simple naming. 
    # For now, we'll try to guess Client from the first word or segment.
    
    all_jobs = total_query.all()
    clients = {}
    
    for job in all_jobs:
        if not job.job_name: continue
        
        # 1. Use dedicated client_name field if available
        if getattr(job, "client_name", None):
            client_name = job.client_name
        else:
            # 2. Fallback to heuristic from job_name
            # If it's an automated job, skip the "Auto-Compare" prefix
            display_name = job.job_name
            if display_name.startswith("Auto-Compare "):
                display_name = display_name.replace("Auto-Compare ", "", 1)
            
            normalized_name = display_name.replace("_", " ").replace("-", " ")
            parts = normalized_name.split()
            client_name = parts[0] if parts else "Unknown"
            
            # 3. Known clients fallback
            known_clients = ["Electrolux", "Philips", "Bridgestone", "Nivea", "Loreal"]
            for known in known_clients:
                if known.lower() in job.job_name.lower():
                    client_name = known
                    break
                
        if client_name not in clients:
            clients[client_name] = {"total": 0, "failed": 0, "completed": 0}
            
        clients[client_name]["total"] += 1
        if job.status == JobStatus.COMPLETED:
            clients[client_name]["completed"] += 1
        elif job.status == JobStatus.FAILED:
            clients[client_name]["failed"] += 1
            
    # Sort clients by total jobs desc
    sorted_clients = sorted(
        [{"name": k, **v} for k, v in clients.items()], 
        key=lambda x: x["total"], 
        reverse=True
    )[:10] # Top 10
    
    # Storage Stats (Existing logic)
    files = db.query(File).all()
    total_size_bytes = 0
    upload_dir = Path("new_video_compare/backend/uploads")
    if not upload_dir.exists():
        upload_dir = Path("uploads")
    if upload_dir.exists():
        try:
            total_size_bytes = get_dir_size(str(upload_dir))
        except: pass
        
    # Database Size and KB Count
    db_size_bytes = 0
    db_path = Path("new_video_compare.db")
    if db_path.exists():
        db_size_bytes = db_path.stat().st_size
    kb_count = db.query(QADecision).count()

    # 5. Recent Logs (Last 10)
    recent_logs = (
        db.query(AutomationLog)
        .order_by(AutomationLog.created_at.desc())
        .limit(10)
        .all()
    )
    logs_data = [
        {
            "id": log.id,
            "cradle_id": log.cradle_id,
            "component": log.component,
            "action": log.action,
            "message": log.message,
            "is_error": log.is_error,
            "created_at": log.created_at.isoformat() if getattr(log, 'created_at', None) else None
        }
        for log in recent_logs
    ]
        
    return {
        "kpi": {
            "total_jobs": total_jobs,
            "active_jobs": processing,
            "success_rate": success_rate,
            "avg_processing_time": round(avg_duration, 1),
            "throughput_24h": jobs_24h
        },
        "chart_data": chart_data,
        "breakdown": {
            "completed": completed,
            "failed": failed,
            "pending": processing
        },
        "clients": sorted_clients,
        "storage": {
            "total_size_gb": round(total_size_bytes / (1024**3), 2),
            "file_count": len(files),
            "db_size_mb": round(db_size_bytes / (1024**2), 2),
            "kb_count": kb_count
        },
        "recent_logs": logs_data
    }

@router.delete("/cleanup")
async def cleanup_old_jobs(days: int = 14, count: int = 50, db: Session = Depends(get_db)):
    """Delete jobs and files older than N days, up to a maximum count."""
    
    import shutil
    from datetime import datetime, timedelta
    
    threshold_date = datetime.now() - timedelta(days=days)
    
    # Find jobs that are completed or failed and older than the threshold
    jobs_to_delete = (
        db.query(ComparisonJob)
        .filter(
            ComparisonJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
            ComparisonJob.created_at < threshold_date
        )
        .order_by(ComparisonJob.created_at.asc())
        .limit(count)
        .all()
    )
    
    deleted_count = 0
    freed_space_bytes = 0

    for job in jobs_to_delete:
        # 1. Identify files to potentially delete
        files_to_check = [job.acceptance_file, job.emission_file]
        
        # 2. Delete the job first (cascade deletes results)
        try:
            db.delete(job)
            db.flush()
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting job {job.id}: {e}")
            continue

        # 3. Check if files are orphaned and delete them
        for file_model in files_to_check:
            if file_model:
                try:
                    # Check if file is used by ANY other job
                    usage_count = db.query(ComparisonJob).filter(
                        or_(
                            ComparisonJob.acceptance_file_id == file_model.id,
                            ComparisonJob.emission_file_id == file_model.id
                        )
                    ).count()
                    
                    if usage_count == 0:
                        # File is orphan, safe to delete
                        file_path = Path(file_model.file_path)
                        if file_path.exists():
                            size = file_path.stat().st_size
                            freed_space_bytes += size
                            os.remove(file_path)
                        
                        # Also delete proxy files for this file
                        proxy_dir = file_path.parent / "proxies"
                        if proxy_dir.exists():
                            # Proxy filenames contain the original file's stem
                            stem = file_path.stem
                            for proxy_file in proxy_dir.iterdir():
                                if stem in proxy_file.name:
                                    freed_space_bytes += proxy_file.stat().st_size
                                    proxy_file.unlink()

                        # Remove parent dir if it's empty and not "uploads"
                        if file_path.parent.name != "uploads" and file_path.parent.exists():
                            try:
                                os.rmdir(file_path.parent)
                            except:
                                pass
                                
                        db.delete(file_model)
                except Exception as e:
                    print(f"Error deleting file {file_model.id}: {e}")
    
    # 4. Clean up orphan File records (DB rows with no referencing jobs)
    all_file_ids_in_jobs = set()
    for job in db.query(ComparisonJob).all():
        if job.acceptance_file_id:
            all_file_ids_in_jobs.add(job.acceptance_file_id)
        if job.emission_file_id:
            all_file_ids_in_jobs.add(job.emission_file_id)
    
    orphan_files = db.query(File).filter(~File.id.in_(all_file_ids_in_jobs)).all() if all_file_ids_in_jobs else db.query(File).all()
    orphan_count = 0
    for orphan in orphan_files:
        try:
            file_path = Path(orphan.file_path)
            if file_path.exists():
                freed_space_bytes += file_path.stat().st_size
                os.remove(file_path)
            db.delete(orphan)
            orphan_count += 1
        except Exception as e:
            print(f"Error deleting orphan file {orphan.id}: {e}")
    
    # 5. Clean temp directory
    upload_base = Path("uploads")
    if not upload_base.exists():
        upload_base = Path("new_video_compare/backend/uploads")
    temp_dir = upload_base / "temp"
    if temp_dir.exists():
        for temp_file in temp_dir.iterdir():
            try:
                if temp_file.is_file():
                    freed_space_bytes += temp_file.stat().st_size
                    temp_file.unlink()
                elif temp_file.is_dir():
                    size = get_dir_size(str(temp_file))
                    freed_space_bytes += size
                    shutil.rmtree(temp_file)
            except Exception as e:
                print(f"Error deleting temp file {temp_file}: {e}")
    
    # 6. Clean orphan proxy files (proxies for files no longer on disk)
    proxy_dir = upload_base / "proxies"
    if proxy_dir.exists():
        # Get stems of all files still referenced by active jobs
        active_stems = set()
        for fid in all_file_ids_in_jobs:
            f = db.query(File).get(fid)
            if f:
                active_stems.add(Path(f.file_path).stem)
        
        for proxy_file in proxy_dir.iterdir():
            if proxy_file.is_file():
                # Check if any active file stem is a substring of the proxy filename
                is_active = any(stem in proxy_file.name for stem in active_stems)
                if not is_active:
                    try:
                        freed_space_bytes += proxy_file.stat().st_size
                        proxy_file.unlink()
                    except Exception as e:
                        print(f"Error deleting proxy {proxy_file}: {e}")
    
    db.commit()
    
    return {
        "message": f"Cleanup finished. Deleted {deleted_count} jobs, {orphan_count} orphan file records.",
        "deleted_jobs": deleted_count,
        "orphan_files_cleaned": orphan_count,
        "days_threshold": days,
        "freed_space_mb": round(freed_space_bytes / (1024 * 1024), 2)
    }

@router.post("/logs")
async def create_automation_log(log: AutomationLogCreate, db: Session = Depends(get_db)):
    """Create a new automation log entry"""
    new_log = AutomationLog(
        cradle_id=log.cradle_id,
        component=log.component,
        action=log.action,
        message=log.message,
        is_error=log.is_error,
        details=log.details
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {"success": True, "log_id": new_log.id}


@router.get("/knowledge-base")
async def get_knowledge_base(
    client_name: Optional[str] = None,
    verdict: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get QA decisions for the Knowledge Base, with optional filtering."""
    from models.models import QADecision

    query = db.query(QADecision)
    if client_name:
        query = query.filter(QADecision.client_name.ilike(f"%{client_name}%"))
    if verdict:
        from models.models import DecisionVerdict
        try:
            query = query.filter(QADecision.verdict == DecisionVerdict(verdict))
        except ValueError:
            pass

    total = query.count()
    decisions = query.order_by(QADecision.created_at.desc()).offset(skip).limit(limit).all()

    # Enrich with job name
    results = []
    for d in decisions:
        job = db.query(ComparisonJob).filter(ComparisonJob.id == d.job_id).first()
        results.append({
            "id": d.id,
            "job_id": d.job_id,
            "job_name": job.job_name if job else getattr(d, 'job_name', None),
            "verdict": d.verdict.value,
            "reasoning": d.reasoning,
            "ai_reasoning": getattr(d, 'ai_reasoning', None),
            "client_name": d.client_name,
            "cradle_id": d.cradle_id,
            "decided_by": d.decided_by,
            "metrics_snapshot": d.metrics_snapshot,
            "knowledge_snapshot": getattr(d, 'knowledge_snapshot', None),
            "created_at": d.created_at.isoformat() if getattr(d, 'created_at', None) else None,
        })

    # Unique clients for filter dropdown
    all_clients = [
        row[0] for row in db.query(QADecision.client_name)
        .distinct()
        .filter(QADecision.client_name.isnot(None))
        .all()
    ]

    return {
        "total": total,
        "results": results,
        "clients": sorted(all_clients),
    }

@router.get("/automation-logs")
async def get_automation_logs(
    skip: int = 0,
    limit: int = 50,
    component: Optional[str] = None,
    only_errors: bool = False,
    cradle_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get automation logs with filtering and pagination."""
    query = db.query(AutomationLog)
    
    if component:
        query = query.filter(AutomationLog.component == component)
    if only_errors:
        query = query.filter(AutomationLog.is_error == True)
    if cradle_id:
        query = query.filter(AutomationLog.cradle_id.ilike(f"%{cradle_id}%"))
        
    total = query.count()
    logs = query.order_by(AutomationLog.created_at.desc()).offset(skip).limit(limit).all()
    
    results = [
        {
            "id": log.id,
            "cradle_id": log.cradle_id,
            "component": log.component,
            "action": log.action,
            "message": log.message,
            "is_error": log.is_error,
            "details": log.details,
            "created_at": log.created_at.isoformat() if getattr(log, 'created_at', None) else None
        }
        for log in logs
    ]
    
    # Get distinct components for filtering dropdown
    all_components = [
        row[0] for row in db.query(AutomationLog.component)
        .distinct()
        .filter(AutomationLog.component.isnot(None))
        .all()
    ]
    
    return {
        "total": total,
        "results": results,
        "components": sorted(all_components)
    }

@router.get("/kb/export/csv")
async def export_kb_csv(
    client_name: Optional[str] = None,
    verdict: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export Knowledge Base to CSV"""
    query = db.query(QADecision)
    if client_name:
        query = query.filter(QADecision.client_name.ilike(f"%{client_name}%"))
    if verdict:
        try:
            query = query.filter(QADecision.verdict == DecisionVerdict(verdict))
        except ValueError:
            pass
            
    decisions = query.order_by(QADecision.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["ID", "Date", "Cradle ID", "Client", "Verdict", "Reasoning", "Decided By"])
    
    for d in decisions:
        writer.writerow([
            d.id,
            d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "",
            d.cradle_id or "",
            d.client_name or "",
            d.verdict.value,
            d.reasoning or "",
            d.decided_by or ""
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=kb_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@router.get("/kb/export/pdf")
async def export_kb_pdf(
    client_name: Optional[str] = None,
    verdict: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export Knowledge Base to PDF"""
    query = db.query(QADecision)
    if client_name:
        query = query.filter(QADecision.client_name.ilike(f"%{client_name}%"))
    if verdict:
        try:
            query = query.filter(QADecision.verdict == DecisionVerdict(verdict))
        except ValueError:
            pass
            
    decisions = query.order_by(QADecision.created_at.desc()).all()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    elements.append(Paragraph("QA Knowledge Base Export", styles['Title']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph("<br/><br/>", styles['Normal']))
    
    # Table data
    data = [["Date", "Cradle ID", "Client", "Verdict", "Decided By"]]
    for d in decisions:
        data.append([
            d.created_at.strftime("%Y-%m-%d") if d.created_at else "",
            d.cradle_id or "",
            d.client_name or "",
            d.verdict.value,
            d.decided_by or ""
        ])
    
    # Create Table
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=kb_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
    )

@router.get("/kb/export/json")
async def export_kb_json(
    client_name: Optional[str] = None,
    verdict: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export Knowledge Base to JSON (full data including snapshots)"""
    query = db.query(QADecision)
    if client_name:
        query = query.filter(QADecision.client_name.ilike(f"%{client_name}%"))
    if verdict:
        try:
            query = query.filter(QADecision.verdict == DecisionVerdict(verdict))
        except ValueError:
            pass
            
    decisions = query.order_by(QADecision.created_at.asc()).all()
    
    import json
    
    # Use an iterator to generate JSON array lazily to avoid OOM
    def generate_json_stream():
        yield "[\n"
        for i, d in enumerate(decisions):
            item = {
                "id": d.id,
                "job_id": d.job_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "cradle_id": d.cradle_id,
                "client_name": d.client_name,
                "verdict": d.verdict.value if d.verdict else None,
                "reasoning": d.reasoning,
                "ai_reasoning": getattr(d, 'ai_reasoning', None),
                "decided_by": d.decided_by,
                "metrics_snapshot": d.metrics_snapshot,
                "knowledge_snapshot": getattr(d, 'knowledge_snapshot', None)
            }
            yield json.dumps(item) + (",\n" if i < len(decisions) - 1 else "\n")
        yield "]\n"
    
    return StreamingResponse(
        generate_json_stream(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=cradle_kb_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
    )



