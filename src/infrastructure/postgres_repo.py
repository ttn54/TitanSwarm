import asyncio
import json
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import String, Text, LargeBinary, Enum as SQLEnum, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from src.core.repository import JobRepository
from src.core.models import Job, JobStatus, UserProfile

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
    required_skills: Mapped[str] = mapped_column(String, default="[]")
    custom_questions: Mapped[str] = mapped_column(String, default="[]")

    def to_pydantic(self) -> Job:
        return Job(
            id=self.id,
            company=self.company,
            role=self.role,
            status=self.status,
            job_description=self.job_description,
            url=self.url,
            required_skills=json.loads(self.required_skills) if self.required_skills else [],
            custom_questions=json.loads(self.custom_questions) if self.custom_questions else [],
        )


class UserProfileModel(Base):
    __tablename__ = "user_profile"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    name: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    github: Mapped[str] = mapped_column(String, default="")
    linkedin: Mapped[str] = mapped_column(String, default="")
    website: Mapped[str] = mapped_column(String, default="")
    base_summary: Mapped[str] = mapped_column(Text, default="")
    skills_json: Mapped[str] = mapped_column(String, default="[]")
    experience_json: Mapped[str] = mapped_column(Text, default="[]")

    def to_pydantic(self) -> UserProfile:
        return UserProfile(
            name=self.name,
            email=self.email,
            phone=self.phone,
            github=self.github,
            linkedin=self.linkedin,
            website=self.website,
            base_summary=self.base_summary,
            skills=json.loads(self.skills_json) if self.skills_json else [],
            experience=json.loads(self.experience_json) if self.experience_json else [],
        )


class TailoredResultModel(Base):
    __tablename__ = "tailored_results"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    ai_json: Mapped[str] = mapped_column(Text)
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary)


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

    # ── Job CRUD ──

    async def save_job(self, job: Job) -> bool:
        """Upserts a job into the database."""
        async with self.async_session() as session:
            stmt_params = {
                "id": job.id,
                "company": job.company,
                "role": job.role,
                "status": job.status,
                "job_description": job.job_description,
                "url": job.url,
                "required_skills": json.dumps(job.required_skills),
                "custom_questions": json.dumps(job.custom_questions),
            }

            if self.is_postgres:
                stmt = postgres_insert(JobModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'id'}
                )
            else:
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

    async def update_status(self, job_id: str, status: JobStatus) -> bool:
        """Transitions a job to a new status."""
        async with self.async_session() as session:
            result = await session.execute(select(JobModel).where(JobModel.id == job_id))
            job_model = result.scalar_one_or_none()
            if job_model is None:
                return False
            job_model.status = status
            await session.commit()
            return True

    async def count_all(self) -> int:
        """Returns the total count of all jobs."""
        async with self.async_session() as session:
            result = await session.execute(select(func.count()).select_from(JobModel))
            return result.scalar() or 0

    # ── UserProfile persistence ──

    async def save_profile(self, profile: UserProfile) -> bool:
        """Upserts the single user profile row."""
        async with self.async_session() as session:
            stmt_params = {
                "id": "default",
                "name": profile.name,
                "email": profile.email,
                "phone": profile.phone,
                "github": profile.github,
                "linkedin": profile.linkedin,
                "website": profile.website,
                "base_summary": profile.base_summary,
                "skills_json": json.dumps(profile.skills),
                "experience_json": json.dumps(profile.experience),
            }

            if self.is_postgres:
                stmt = postgres_insert(UserProfileModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'id'}
                )
            else:
                stmt = sqlite_insert(UserProfileModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'id'}
                )

            try:
                await session.execute(stmt)
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to save profile: {e}")
                await session.rollback()
                return False

    async def get_profile(self) -> Optional[UserProfile]:
        """Returns the saved profile, or None if none exists."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.id == "default")
            )
            model = result.scalar_one_or_none()
            if model:
                return model.to_pydantic()
            return None

    # ── Tailored result persistence ──

    async def save_tailored_result(self, job_id: str, ai_json: str, pdf_bytes: bytes) -> bool:
        """Saves AI tailoring output + generated PDF bytes for a job."""
        async with self.async_session() as session:
            stmt_params = {
                "job_id": job_id,
                "ai_json": ai_json,
                "pdf_bytes": pdf_bytes,
            }

            if self.is_postgres:
                stmt = postgres_insert(TailoredResultModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['job_id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'job_id'}
                )
            else:
                stmt = sqlite_insert(TailoredResultModel).values(**stmt_params)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['job_id'],
                    set_={k: v for k, v in stmt_params.items() if k != 'job_id'}
                )

            try:
                await session.execute(stmt)
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to save tailored result for {job_id}: {e}")
                await session.rollback()
                return False

    async def get_tailored_result(self, job_id: str) -> Optional[Tuple[str, bytes]]:
        """Returns (ai_json, pdf_bytes) for a job, or None if not yet tailored."""
        async with self.async_session() as session:
            result = await session.execute(
                select(TailoredResultModel).where(TailoredResultModel.job_id == job_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return (model.ai_json, model.pdf_bytes)
            return None
