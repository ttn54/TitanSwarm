import asyncio
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import String, Enum as SQLEnum, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from src.core.repository import JobRepository
from src.core.models import Job, JobStatus

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus))
    job_description: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)

    def to_pydantic(self) -> Job:
        return Job(
            id=self.id,
            company=self.company,
            role=self.role,
            status=self.status,
            job_description=self.job_description,
            url=self.url
        )

class PostgresRepository(JobRepository):
    """
    SQLAlchemy-based asynchronous repository for PostgreSQL (and SQLite for testing).
    """
    def __init__(self, dsn: str = "sqlite+aiosqlite:///:memory:"):
        self.engine = create_async_engine(dsn, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.is_postgres = dsn.startswith("postgresql")

    async def init_db(self):
        """Creates tables if they do not exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """Disposes the engine connection pool."""
        await self.engine.dispose()

    async def save_job(self, job: Job) -> bool:
        """Upserts a job into the database."""
        async with self.async_session() as session:
            # Prepare statement based on dialect to handle UPSERT
            stmt_params = {
                "id": job.id,
                "company": job.company,
                "role": job.role,
                "status": job.status,
                "job_description": job.job_description,
                "url": job.url,
            }
            
            if self.is_postgres:
                # PostgreSQL ON CONFLICT DO UPDATE
                stmt = postgres_insert(JobModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'id'}
                )
            else:
                # SQLite ON CONFLICT DO UPDATE
                stmt = sqlite_insert(JobModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'id'}
                )

            try:
                await session.execute(stmt)
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to save job {job.id}: {e}")
                await session.rollback()
                return False

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieves a single job by Hash ID."""
        async with self.async_session() as session:
            result = await session.execute(select(JobModel).where(JobModel.id == job_id))
            job_model = result.scalar_one_or_none()
            if job_model:
                return job_model.to_pydantic()
            return None

    async def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Retrieves all jobs matching a specific status."""
        async with self.async_session() as session:
            result = await session.execute(select(JobModel).where(JobModel.status == status))
            job_models = result.scalars().all()
            return [model.to_pydantic() for model in job_models]
