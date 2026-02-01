
"""
Database Monitor Service.

Monitors PostgreSQL database size to stay within Neon Free Tier limits (500MB).
"""
import logging
import os
from prisma import Prisma

logger = logging.getLogger(__name__)

class DatabaseMonitor:
    
    FREE_TIER_LIMIT_MB = 500
    WARNING_THRESHOLD_MB = 450
    
    @staticmethod
    async def check_storage_usage() -> dict:
        """
        Check current database size.
        Returns dict with size_mb and warning status.
        """
        db = Prisma()
        try:
            await db.connect()
            
            # Execute raw SQL to get database size
            # Current database name is needed, usually extracted from connection or just current DB
            # "pg_database_size(current_database())" returns bytes
            result = await db.query_raw("SELECT pg_database_size(current_database()) as size_bytes;")
            
            # Result is a list of dicts, depending on Prisma's return format
            # Usually [{'size_bytes': 123456}]
            
            if not result:
                return {"size_mb": 0, "status": "unknown"}
                
            size_bytes = int(result[0]['size_bytes'])
            size_mb = size_bytes / (1024 * 1024)
            
            remaining_mb = DatabaseMonitor.FREE_TIER_LIMIT_MB - size_mb
            
            status = {
                "size_mb": round(size_mb, 2),
                "limit_mb": DatabaseMonitor.FREE_TIER_LIMIT_MB,
                "remaining_mb": round(remaining_mb, 2),
                "is_critical": size_mb >= DatabaseMonitor.FREE_TIER_LIMIT_MB,
                "is_warning": size_mb >= DatabaseMonitor.WARNING_THRESHOLD_MB
            }
            
            if status['is_critical']:
                logger.error(f"❌ DATABASE FULL! {size_mb:.2f} MB used of {DatabaseMonitor.FREE_TIER_LIMIT_MB} MB")
            elif status['is_warning']:
                logger.warning(f"⚠️ Database near limit: {size_mb:.2f} MB used")
            else:
                logger.info(f"✅ Database Storage: {size_mb:.2f} MB / {DatabaseMonitor.FREE_TIER_LIMIT_MB} MB")
                
            return status
            
        except Exception as e:
            logger.error(f"Failed to check database monitoring: {e}")
            return {"error": str(e)}
        finally:
            if db.is_connected():
                await db.disconnect()

    @staticmethod
    async def cleanup_old_logs(retain_days: int = 30):
        """
        Placeholder for cleaning up old logs/records if we had a logs table.
        Currently, our schema uses 'Video' records which are main content.
        Deleting them should be a manual user choice via R2 cleanup, 
        which technically deletes the DB record too if cascaded? 
        
        For now, this is a manual admonition to the user.
        """
        pass
