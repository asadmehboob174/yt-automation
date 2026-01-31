"""
Production Configuration and Logging Setup.

Provides structured logging, health checks, and operational utilities.
"""
import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from contextlib import asynccontextmanager


# ============================================
# Logging Configuration
# ============================================

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "video_id"):
            log_obj["video_id"] = record.video_id
        if hasattr(record, "step"):
            log_obj["step"] = record.step
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
        
        return json.dumps(log_obj)


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[Path] = None
):
    """
    Configure logging for production.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON structured logging
        log_file: Optional file path for logs
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured: level={level}, json={json_format}")


# ============================================
# Health Check System
# ============================================

@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    healthy: bool
    message: str = ""
    latency_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self):
        return {
            "name": self.name,
            "healthy": self.healthy,
            "message": self.message,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat()
        }


class HealthChecker:
    """
    Health check runner for all services.
    
    Usage:
        checker = HealthChecker()
        results = await checker.run_all()
        if checker.is_healthy(results):
            print("All systems operational")
    """
    
    async def check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        import time
        start = time.time()
        
        try:
            from prisma import Prisma
            db = Prisma()
            await db.connect()
            
            # Simple query to verify connection
            await db.execute_raw("SELECT 1")
            
            await db.disconnect()
            
            return HealthCheckResult(
                name="database",
                healthy=True,
                message="Connected to Postgres",
                latency_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                healthy=False,
                message=str(e),
                latency_ms=(time.time() - start) * 1000
            )
    
    async def check_r2_storage(self) -> HealthCheckResult:
        """Check R2 storage connectivity."""
        import time
        start = time.time()
        
        try:
            from services.cloud_storage import R2Storage
            storage = R2Storage()
            stats = storage.get_bucket_size()
            
            return HealthCheckResult(
                name="r2_storage",
                healthy=True,
                message=f"Bucket OK: {stats['total_gb']} GB used",
                latency_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return HealthCheckResult(
                name="r2_storage",
                healthy=False,
                message=str(e),
                latency_ms=(time.time() - start) * 1000
            )
    
    async def check_huggingface(self) -> HealthCheckResult:
        """Check HuggingFace API connectivity."""
        import time
        import httpx
        start = time.time()
        
        try:
            token = os.getenv("HF_TOKEN")
            if not token:
                return HealthCheckResult(
                    name="huggingface",
                    healthy=False,
                    message="HF_TOKEN not configured"
                )
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://huggingface.co/api/whoami",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    user = response.json().get("name", "unknown")
                    return HealthCheckResult(
                        name="huggingface",
                        healthy=True,
                        message=f"Authenticated as {user}",
                        latency_ms=(time.time() - start) * 1000
                    )
                else:
                    return HealthCheckResult(
                        name="huggingface",
                        healthy=False,
                        message=f"Auth failed: {response.status_code}",
                        latency_ms=(time.time() - start) * 1000
                    )
        except Exception as e:
            return HealthCheckResult(
                name="huggingface",
                healthy=False,
                message=str(e),
                latency_ms=(time.time() - start) * 1000
            )
    
    async def check_gemini(self) -> HealthCheckResult:
        """Check Gemini API connectivity."""
        import time
        start = time.time()
        
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return HealthCheckResult(
                    name="gemini",
                    healthy=False,
                    message="GEMINI_API_KEY not configured"
                )
            
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # Quick model listing to verify API key
            models = list(genai.list_models())
            
            return HealthCheckResult(
                name="gemini",
                healthy=True,
                message=f"API OK, {len(models)} models available",
                latency_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            return HealthCheckResult(
                name="gemini",
                healthy=False,
                message=str(e),
                latency_ms=(time.time() - start) * 1000
            )
    
    async def check_inngest(self) -> HealthCheckResult:
        """Check Inngest dev server connectivity."""
        import time
        import httpx
        start = time.time()
        
        try:
            inngest_url = os.getenv("INNGEST_BASE_URL", "http://localhost:8288")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{inngest_url}/health", timeout=5)
                
                if response.status_code == 200:
                    return HealthCheckResult(
                        name="inngest",
                        healthy=True,
                        message="Dev server running",
                        latency_ms=(time.time() - start) * 1000
                    )
                else:
                    return HealthCheckResult(
                        name="inngest",
                        healthy=False,
                        message=f"Unhealthy: {response.status_code}",
                        latency_ms=(time.time() - start) * 1000
                    )
        except Exception as e:
            return HealthCheckResult(
                name="inngest",
                healthy=False,
                message=str(e),
                latency_ms=(time.time() - start) * 1000
            )
    
    async def run_all(self) -> list[HealthCheckResult]:
        """Run all health checks concurrently."""
        import asyncio
        
        checks = [
            self.check_database(),
            self.check_r2_storage(),
            self.check_huggingface(),
            self.check_gemini(),
            self.check_inngest(),
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        # Handle any exceptions
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(HealthCheckResult(
                    name=f"check_{i}",
                    healthy=False,
                    message=str(result)
                ))
            else:
                processed.append(result)
        
        return processed
    
    @staticmethod
    def is_healthy(results: list[HealthCheckResult]) -> bool:
        """Check if all results are healthy."""
        return all(r.healthy for r in results)
    
    @staticmethod
    def summary(results: list[HealthCheckResult]) -> dict:
        """Generate summary of health check results."""
        return {
            "healthy": all(r.healthy for r in results),
            "checks": [r.to_dict() for r in results],
            "timestamp": datetime.utcnow().isoformat()
        }


# ============================================
# Backup & Recovery
# ============================================

class BackupManager:
    """Manage backups and recovery procedures."""
    
    def __init__(self, backup_dir: Path = None):
        self.backup_dir = backup_dir or Path("/tmp/video-factory-backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def backup_job_metadata(self, job_id: str, metadata: dict) -> Path:
        """Backup job metadata to JSON file."""
        filename = f"job_{job_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = self.backup_dir / filename
        
        with open(backup_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logging.info(f"💾 Backed up job {job_id} to {backup_path}")
        return backup_path
    
    async def backup_database_jobs(self, older_than_days: int = 90):
        """
        Backup completed jobs older than N days before deletion.
        
        This is part of the free tier management strategy.
        """
        from prisma import Prisma
        from datetime import timedelta
        
        db = Prisma()
        await db.connect()
        
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        
        # Find old completed jobs
        old_jobs = await db.video.find_many(
            where={
                "status": "COMPLETED",
                "createdAt": {"lt": cutoff}
            },
            take=100
        )
        
        # Backup each job
        backed_up = 0
        for job in old_jobs:
            await self.backup_job_metadata(job.id, {
                "id": job.id,
                "title": job.title,
                "status": job.status,
                "script": job.script,
                "metadata": job.metadata,
                "createdAt": job.createdAt,
                "updatedAt": job.updatedAt
            })
            backed_up += 1
        
        await db.disconnect()
        
        logging.info(f"📦 Backed up {backed_up} old jobs")
        return backed_up
    
    async def cleanup_old_jobs(self, older_than_days: int = 90):
        """Delete old completed jobs after backup."""
        backed_up = await self.backup_database_jobs(older_than_days)
        
        if backed_up > 0:
            from prisma import Prisma
            from datetime import timedelta
            
            db = Prisma()
            await db.connect()
            
            cutoff = datetime.utcnow() - timedelta(days=older_than_days)
            
            result = await db.execute_raw(
                f"DELETE FROM videos WHERE status = 'COMPLETED' AND created_at < $1",
                cutoff
            )
            
            await db.disconnect()
            
            logging.info(f"🗑️ Deleted old jobs after backup")


# ============================================
# Monitoring Dashboard Data
# ============================================

class MonitoringData:
    """Collect data for monitoring dashboards."""
    
    async def get_dashboard_stats(self) -> dict:
        """Get stats for dashboard display."""
        from prisma import Prisma
        from services.cloud_storage import R2Storage
        from services.quota_tracker import QuotaTracker
        
        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "jobs": {},
            "storage": {},
            "quota": {}
        }
        
        # Job stats
        try:
            db = Prisma()
            await db.connect()
            
            total = await db.video.count()
            completed = await db.video.count(where={"status": "COMPLETED"})
            failed = await db.video.count(where={"status": "FAILED"})
            processing = await db.video.count(where={"status": "PROCESSING"})
            
            stats["jobs"] = {
                "total": total,
                "completed": completed,
                "failed": failed,
                "processing": processing,
                "success_rate": round((completed / total * 100) if total > 0 else 0, 1)
            }
            
            await db.disconnect()
        except Exception as e:
            stats["jobs"]["error"] = str(e)
        
        # Storage stats
        try:
            storage = R2Storage()
            storage_stats = storage.get_bucket_size()
            stats["storage"] = {
                "used_gb": storage_stats["total_gb"],
                "remaining_gb": storage_stats["free_tier_remaining_gb"],
                "object_count": storage_stats["object_count"],
                "usage_percent": round((storage_stats["total_gb"] / 10) * 100, 1)
            }
        except Exception as e:
            stats["storage"]["error"] = str(e)
        
        # Quota stats
        try:
            tracker = QuotaTracker()
            remaining = await tracker.get_remaining_seconds()
            stats["quota"] = {
                "gpu_seconds_remaining": remaining,
                "gpu_minutes_remaining": round(remaining / 60, 1)
            }
        except Exception as e:
            stats["quota"]["error"] = str(e)
        
        return stats


# ============================================
# Runbook Commands
# ============================================

async def runbook_full_health_check():
    """Run full health check and print results."""
    setup_logging(level="INFO")
    
    checker = HealthChecker()
    results = await checker.run_all()
    
    print("\n" + "="*50)
    print("HEALTH CHECK RESULTS")
    print("="*50)
    
    for result in results:
        emoji = "✅" if result.healthy else "❌"
        print(f"{emoji} {result.name}: {result.message} ({result.latency_ms:.0f}ms)")
    
    print("="*50)
    overall = "HEALTHY" if checker.is_healthy(results) else "UNHEALTHY"
    print(f"Overall: {overall}")
    print("="*50 + "\n")
    
    return checker.is_healthy(results)


async def runbook_dashboard_stats():
    """Get dashboard stats."""
    monitor = MonitoringData()
    stats = await monitor.get_dashboard_stats()
    print(json.dumps(stats, indent=2))
    return stats


if __name__ == "__main__":
    import asyncio
    
    print("Production Utilities")
    print("="*50)
    print("Available commands:")
    print("  python production.py health   - Run health checks")
    print("  python production.py stats    - Get dashboard stats")
    print("  python production.py backup   - Backup old jobs")
    print("="*50)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "health":
            asyncio.run(runbook_full_health_check())
        elif cmd == "stats":
            asyncio.run(runbook_dashboard_stats())
        elif cmd == "backup":
            backup = BackupManager()
            asyncio.run(backup.backup_database_jobs(90))
