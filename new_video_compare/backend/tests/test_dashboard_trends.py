import unittest
import asyncio
from datetime import datetime, timedelta
import httpx
from httpx import ASGITransport
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event

from api.v1.dashboard import router, ChartRange
from models.database import Base, get_db
from models.models import ComparisonJob, JobStatus, File, FileType, FileFormat
import uuid

app = FastAPI()
app.include_router(router, prefix="/dashboard")

class TestDashboardTrends(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # Temporarily make created_at nullable for testing NULL handling
        original_nullable = ComparisonJob.__table__.c.created_at.nullable
        ComparisonJob.__table__.c.created_at.nullable = True
        Base.metadata.create_all(bind=self.engine)
        ComparisonJob.__table__.c.created_at.nullable = original_nullable
        self.db = self.SessionLocal()
        
        def override_get_db():
            try:
                yield self.db
            finally:
                pass
                
        app.dependency_overrides[get_db] = override_get_db
        
        transport = ASGITransport(app=app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        
        self.query_count = 0
        self.executed_statements = []
        @event.listens_for(self.engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            self.query_count += 1
            self.executed_statements.append(statement)
            
    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def insert_job(self, created_at, status=JobStatus.COMPLETED):
        uid = str(uuid.uuid4())
        f1 = File(filename=f"f1_{uid}.mp4", original_name=f"f1_{uid}.mp4", file_path=f"f1_{uid}", file_size=10, file_type=FileType.ACCEPTANCE, file_format=FileFormat.MP4)
        f2 = File(filename=f"f2_{uid}.mp4", original_name=f"f2_{uid}.mp4", file_path=f"f2_{uid}", file_size=10, file_type=FileType.EMISSION, file_format=FileFormat.MP4)
        self.db.add(f1)
        self.db.add(f2)
        self.db.commit()
        job = ComparisonJob(
            job_name="test_job",
            acceptance_file_id=f1.id,
            emission_file_id=f2.id,
            status=status,
            created_at=created_at,
            processing_duration=10
        )
        self.db.add(job)
        self.db.commit()
        return job

    async def test_null_created_at_ignored(self):
        uid = str(uuid.uuid4())
        f1 = File(filename=f"f1_{uid}.mp4", original_name=f"f1_{uid}.mp4", file_path=f"f1_{uid}", file_size=10, file_type=FileType.ACCEPTANCE, file_format=FileFormat.MP4)
        f2 = File(filename=f"f2_{uid}.mp4", original_name=f"f2_{uid}.mp4", file_path=f"f2_{uid}", file_size=10, file_type=FileType.EMISSION, file_format=FileFormat.MP4)
        self.db.add(f1)
        self.db.add(f2)
        self.db.commit()
        self.db.execute(text(
            "INSERT INTO comparison_jobs (job_name, comparison_type, sensitivity_level, status, processing_duration, created_at, acceptance_file_id, emission_file_id) "
            f"VALUES ('null_job', 'FULL', 'MEDIUM', 'COMPLETED', 10, NULL, {f1.id}, {f2.id})"
        ))
        self.db.commit()
        
        response = await self.client.get("/dashboard/stats?range=all")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(len(data["chart_data"]) >= 1)
        self.assertEqual(data["chart_data"][0]["count"], 0)

    async def test_fastapi_endpoints_ranges(self):
        for r in ["7d", "30d", "90d", "all"]:
            response = await self.client.get(f"/dashboard/stats?range={r}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("chart_data", data)
            
        response = await self.client.get("/dashboard/stats?range=invalid")
        self.assertEqual(response.status_code, 422)

    async def test_7d_range_padding(self):
        now = datetime.utcnow()
        self.insert_job(now - timedelta(days=2))
        self.insert_job(now - timedelta(days=5))
        
        response = await self.client.get("/dashboard/stats?range=7d")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(len(data["chart_data"]), 7)
        counts = [d["count"] for d in data["chart_data"]]
        self.assertEqual(sum(counts), 2)
        
    async def test_all_range_monthly_padding(self):
        now = datetime.utcnow()
        old_date = now - timedelta(days=95)
        self.insert_job(old_date)
        self.insert_job(now)
        
        response = await self.client.get("/dashboard/stats?range=all")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertGreaterEqual(len(data["chart_data"]), 4)
        counts = [d["count"] for d in data["chart_data"]]
        self.assertEqual(sum(counts), 2)
        
    async def test_query_counts(self):
        for range_val in ["7d", "30d", "90d", "all"]:
            self.executed_statements.clear()
            await self.client.get(f"/dashboard/stats?range={range_val}")
            
            # Znajdź zapytanie pobierające dane do wykresu. 
            # Musi posiadać GROUP BY i funkcję czasu (date albo strftime).
            chart_queries = [stmt for stmt in self.executed_statements if "GROUP BY" in stmt.upper() and ("strftime" in stmt.lower() or "date" in stmt.lower())]
            
            # Wymagane jest dokładnie JEDNO zapytanie agregujące dla wykresu (brak problemu N+1)
            self.assertEqual(len(chart_queries), 1, f"Failed for range {range_val}: Expected exactly 1 chart aggregation query, found {len(chart_queries)}")

if __name__ == '__main__':
    unittest.main()
