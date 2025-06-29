"""
Database configuration and initialization
PostgreSQL with TimescaleDB for time-series data
"""

import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

# Database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True if settings.ENVIRONMENT == "development" else False,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for database models"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database and create tables"""
    try:
        logger.info("Initializing database...")
        
        # Test database connection
        async with engine.begin() as conn:
            # Check if TimescaleDB extension is available
            result = await conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
            )
            has_timescaledb = result.scalar()
            
            if has_timescaledb:
                logger.info("TimescaleDB extension detected")
            else:
                logger.warning("TimescaleDB extension not found - time-series optimization unavailable")
            
            # Create database schema
            await conn.run_sync(Base.metadata.create_all)
            
            # Initialize TimescaleDB hypertables if available
            if has_timescaledb:
                await init_timescale_tables(conn)
        
        logger.info("Database initialization completed")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def init_timescale_tables(conn):
    """Initialize TimescaleDB hypertables for time-series data"""
    try:
        # Device metrics hypertable
        await conn.execute(text("""
            SELECT create_hypertable(
                'device_metrics', 
                'timestamp',
                chunk_time_interval => INTERVAL '1 hour',
                if_not_exists => TRUE
            )
        """))
        
        # Add space partitioning by device_id
        await conn.execute(text("""
            SELECT add_dimension(
                'device_metrics', 
                'device_id', 
                number_partitions => 16,
                if_not_exists => TRUE
            )
        """))
        
        # System logs hypertable
        await conn.execute(text("""
            SELECT create_hypertable(
                'system_logs', 
                'timestamp',
                chunk_time_interval => INTERVAL '6 hours',
                if_not_exists => TRUE
            )
        """))
        
        # Network events hypertable
        await conn.execute(text("""
            SELECT create_hypertable(
                'network_events', 
                'timestamp',
                chunk_time_interval => INTERVAL '1 hour',
                if_not_exists => TRUE
            )
        """))
        
        # Backup events hypertable
        await conn.execute(text("""
            SELECT create_hypertable(
                'backup_events', 
                'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            )
        """))
        
        # Create continuous aggregates for performance
        await create_continuous_aggregates(conn)
        
        # Set up data retention policies
        await setup_retention_policies(conn)
        
        # Enable compression for old data
        await enable_compression(conn)
        
        logger.info("TimescaleDB hypertables initialized successfully")
        
    except Exception as e:
        logger.error(f"TimescaleDB initialization failed: {e}")
        # Don't raise - continue without TimescaleDB features


async def create_continuous_aggregates(conn):
    """Create continuous aggregates for common queries"""
    try:
        # Hourly device metrics aggregate
        await conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS device_metrics_hourly
            WITH (timescaledb.continuous) AS
            SELECT 
                time_bucket('1 hour', timestamp) AS bucket,
                device_id,
                metric_type,
                AVG(value) as avg_value,
                MAX(value) as max_value,
                MIN(value) as min_value,
                COUNT(*) as sample_count,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_value
            FROM device_metrics
            GROUP BY bucket, device_id, metric_type;
        """))
        
        # Daily device metrics aggregate
        await conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS device_metrics_daily
            WITH (timescaledb.continuous) AS
            SELECT 
                time_bucket('1 day', timestamp) AS bucket,
                device_id,
                metric_type,
                AVG(value) as avg_value,
                MAX(value) as max_value,
                MIN(value) as min_value,
                COUNT(*) as sample_count
            FROM device_metrics
            GROUP BY bucket, device_id, metric_type;
        """))
        
        # Add refresh policies
        await conn.execute(text("""
            SELECT add_continuous_aggregate_policy(
                'device_metrics_hourly',
                start_offset => INTERVAL '3 hours',
                end_offset => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour',
                if_not_exists => TRUE
            );
        """))
        
        await conn.execute(text("""
            SELECT add_continuous_aggregate_policy(
                'device_metrics_daily',
                start_offset => INTERVAL '2 days',
                end_offset => INTERVAL '1 day',
                schedule_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            );
        """))
        
        logger.info("Continuous aggregates created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create continuous aggregates: {e}")


async def setup_retention_policies(conn):
    """Set up data retention policies"""
    try:
        # Keep device metrics for 1 year
        await conn.execute(text("""
            SELECT add_retention_policy(
                'device_metrics', 
                INTERVAL '1 year',
                if_not_exists => TRUE
            );
        """))
        
        # Keep system logs for 6 months
        await conn.execute(text("""
            SELECT add_retention_policy(
                'system_logs', 
                INTERVAL '6 months',
                if_not_exists => TRUE
            );
        """))
        
        # Keep network events for 3 months
        await conn.execute(text("""
            SELECT add_retention_policy(
                'network_events', 
                INTERVAL '3 months',
                if_not_exists => TRUE
            );
        """))
        
        # Keep backup events for 2 years
        await conn.execute(text("""
            SELECT add_retention_policy(
                'backup_events', 
                INTERVAL '2 years',
                if_not_exists => TRUE
            );
        """))
        
        logger.info("Retention policies configured successfully")
        
    except Exception as e:
        logger.error(f"Failed to setup retention policies: {e}")


async def enable_compression(conn):
    """Enable compression for time-series tables"""
    try:
        # Enable compression on device_metrics after 7 days
        await conn.execute(text("""
            ALTER TABLE device_metrics SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'device_id',
                timescaledb.compress_orderby = 'timestamp DESC'
            );
        """))
        
        await conn.execute(text("""
            SELECT add_compression_policy(
                'device_metrics', 
                INTERVAL '7 days',
                if_not_exists => TRUE
            );
        """))
        
        # Enable compression on system_logs after 1 day
        await conn.execute(text("""
            ALTER TABLE system_logs SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'timestamp DESC'
            );
        """))
        
        await conn.execute(text("""
            SELECT add_compression_policy(
                'system_logs', 
                INTERVAL '1 day',
                if_not_exists => TRUE
            );
        """))
        
        logger.info("Compression policies enabled successfully")
        
    except Exception as e:
        logger.error(f"Failed to enable compression: {e}")


async def health_check() -> dict:
    """Database health check"""
    try:
        async with engine.begin() as conn:
            # Test basic connectivity
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
            
            # Check TimescaleDB status
            result = await conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
            )
            has_timescaledb = result.scalar()
            
            # Get database size
            result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            db_size = result.scalar()
            
            # Get active connections
            result = await conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_connections = result.scalar()
            
            return {
                "status": "healthy",
                "timescaledb_enabled": has_timescaledb,
                "database_size": db_size,
                "active_connections": active_connections
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }