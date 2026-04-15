import asyncio
import json
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import String, Text, LargeBinary, Integer, Enum as SQLEnum, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from src.core.repository import JobRepository
from src.core.models import Job, JobStatus, UserProfile

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)


class UserLedgerModel(Base):
    __tablename__ = "user_ledgers"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, default="")


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
    location: Mapped[str] = mapped_column(String, default="")
    date_posted: Mapped[str] = mapped_column(String, default="")
    user_id: Mapped[int] = mapped_column(Integer, default=1)

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
            location=self.location or "",
            date_posted=self.date_posted or "",
        )


class UserProfileModel(Base):
    __tablename__ = "user_profile"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    github: Mapped[str] = mapped_column(String, default="")
    linkedin: Mapped[str] = mapped_column(String, default="")
    website: Mapped[str] = mapped_column(String, default="")
    base_summary: Mapped[str] = mapped_column(Text, default="")
    skills_json: Mapped[str] = mapped_column(String, default="[]")
    experience_json: Mapped[str] = mapped_column(Text, default="[]")
    pref_role: Mapped[str] = mapped_column(String, default="")
    pref_location: Mapped[str] = mapped_column(String, default="")

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
            pref_role=self.pref_role or "",
            pref_location=self.pref_location or "",
        )


class TailoredResultModel(Base):
    __tablename__ = "tailored_results"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    ai_json: Mapped[str] = mapped_column(Text)
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    user_id: Mapped[int] = mapped_column(Integer, default=1)


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
        """Creates tables if they do not exist, then migrates new columns."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # SQLite does not re-add columns on create_all for existing tables,
        # so we manually add new columns with a PRAGMA check.
        await self._ensure_columns()

    async def _ensure_columns(self):
        """Adds columns that may be missing from an older DB schema."""
        new_columns = [
            ("jobs",             "location",    "TEXT DEFAULT ''"),
            ("jobs",             "date_posted",  "TEXT DEFAULT ''"),
            ("jobs",             "user_id",      "INTEGER DEFAULT 1"),
            ("user_profile",     "user_id",      "INTEGER DEFAULT 1"),
            ("tailored_results", "user_id",      "INTEGER DEFAULT 1"),
        ]
        async with self.engine.begin() as conn:
            for table, col, col_def in new_columns:
                try:
                    existing = await conn.run_sync(
                        lambda sync_conn, t=table: [
                            row[1] for row in sync_conn.execute(
                                __import__('sqlalchemy').text(f"PRAGMA table_info({t})")
                            ).fetchall()
                        ]
                    )
                    if col not in existing:
                        await conn.execute(
                            __import__('sqlalchemy').text(
                                f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"
                            )
                        )
                        logger.info(f"Migration: added column '{col}' to '{table}'")
                except Exception:
                    pass  # table doesn't exist yet — create_all will handle it

    async def close(self):
        """Disposes the engine connection pool."""
        await self.engine.dispose()

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def create_user(self, username: str, password: str) -> int:
        """
        Hash the password with bcrypt and insert a new user row.
        Returns the new user_id.
        Raises ValueError if the username is already taken.
        """
        import bcrypt
        existing = await self.get_user_by_username(username)
        if existing is not None:
            raise ValueError(f"Username '{username}' already exists")
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        async with self.async_session() as session:
            user = UserModel(username=username, password_hash=hashed)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user.id

    async def get_user_by_username(self, username: str) -> dict | None:
        """Returns {'id': int, 'username': str, 'password_hash': str} or None."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username)
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return {"id": model.id, "username": model.username, "password_hash": model.password_hash}

    async def verify_user(self, username: str, password: str) -> int | None:
        """
        Verify username + password.
        Returns user_id on success, None on failure.
        """
        import bcrypt
        user = await self.get_user_by_username(username)
        if user is None:
            return None
        if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return user["id"]
        return None

    # ── Per-user ledger ───────────────────────────────────────────────────────

    async def get_ledger(self, user_id: int) -> str:
        """Returns the ledger content for a user, or '' if none saved yet."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserLedgerModel).where(UserLedgerModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            return model.content if model else ""

    async def save_ledger(self, user_id: int, content: str) -> None:
        """Upserts the ledger content for a user."""
        async with self.async_session() as session:
            if self.is_postgres:
                stmt = postgres_insert(UserLedgerModel).values(user_id=user_id, content=content)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id"], set_={"content": content}
                )
            else:
                stmt = sqlite_insert(UserLedgerModel).values(user_id=user_id, content=content)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id"], set_={"content": content}
                )
            await session.execute(stmt)
            await session.commit()

    # ── Job CRUD ──

    async def save_job(self, job: Job, user_id: int = 1) -> bool:
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
                "location": job.location or "",
                "date_posted": job.date_posted or "",
                "user_id": user_id,
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

    async def get_job(self, job_id: str, user_id: int = 1) -> Optional[Job]:
        """Retrieves a single job by Hash ID, scoped to user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.id == job_id, JobModel.user_id == user_id)
            )
            job_model = result.scalar_one_or_none()
            if job_model:
                return job_model.to_pydantic()
            return None

    async def get_jobs_by_status(self, status: JobStatus, user_id: int = 1) -> List[Job]:
        """Retrieves all jobs matching a specific status, scoped to user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.status == status, JobModel.user_id == user_id)
            )
            job_models = result.scalars().all()
            return [model.to_pydantic() for model in job_models]

    async def update_status(self, job_id: str, status: JobStatus, user_id: int = 1) -> bool:
        """Transitions a job to a new status."""
        async with self.async_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.id == job_id, JobModel.user_id == user_id)
            )
            job_model = result.scalar_one_or_none()
            if job_model is None:
                return False
            job_model.status = status
            await session.commit()
            return True

    async def count_all(self, user_id: int = 1) -> int:
        """Returns the total count of all jobs for a user."""
        async with self.async_session() as session:
            result = await session.execute(
                select(func.count()).select_from(JobModel).where(JobModel.user_id == user_id)
            )
            return result.scalar() or 0

    async def delete_jobs_by_status(self, status: JobStatus, user_id: int = 1) -> int:
        """Deletes all jobs with the given status for a user. Returns count deleted."""
        async with self.async_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.status == status, JobModel.user_id == user_id)
            )
            jobs = result.scalars().all()
            count = len(jobs)
            for job in jobs:
                await session.delete(job)
            await session.commit()
            return count

    # ── UserProfile persistence ──

    async def save_profile(self, profile: UserProfile, user_id: int = 1) -> bool:
        """Upserts the user profile row for a specific user."""
        async with self.async_session() as session:
            stmt_params = {
                "id": f"user_{user_id}",
                "user_id": user_id,
                "name": profile.name,
                "email": profile.email,
                "phone": profile.phone,
                "github": profile.github,
                "linkedin": profile.linkedin,
                "website": profile.website,
                "base_summary": profile.base_summary,
                "skills_json": json.dumps(profile.skills),
                "experience_json": json.dumps(profile.experience),
                "pref_role": profile.pref_role,
                "pref_location": profile.pref_location,
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

    async def get_profile(self, user_id: int = 1) -> Optional[UserProfile]:
        """Returns the saved profile for a user, or None if none exists."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.user_id == user_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return model.to_pydantic()
            return None

    # ── Tailored result persistence ──

    async def save_tailored_result(self, job_id: str, ai_json: str, pdf_bytes: bytes, cover_letter: str | None = None, user_id: int = 1) -> bool:
        """Saves AI tailoring output + generated PDF bytes + optional cover letter for a job."""
        async with self.async_session() as session:
            stmt_params = {
                "job_id": job_id,
                "ai_json": ai_json,
                "pdf_bytes": pdf_bytes,
                "cover_letter_text": cover_letter,
                "user_id": user_id,
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

    async def get_tailored_result(self, job_id: str, user_id: int = 1) -> Optional[Tuple[str, bytes, str | None]]:
        """Returns (ai_json, pdf_bytes, cover_letter) for a job, or None if not yet tailored."""
        async with self.async_session() as session:
            result = await session.execute(
                select(TailoredResultModel).where(
                    TailoredResultModel.job_id == job_id,
                    TailoredResultModel.user_id == user_id,
                )
            )
            model = result.scalar_one_or_none()
            if model:
                return (model.ai_json, model.pdf_bytes, model.cover_letter_text)
            return None

    async def get_all_user_targets(self) -> list[tuple[int, str, str]]:
        """
        Returns (user_id, pref_role, pref_location) for every user whose
        profile has a non-empty pref_role.  Used by the Sourcing Daemon.
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(UserProfileModel).where(UserProfileModel.pref_role != "")
            )
            rows = result.scalars().all()
            return [(row.user_id, row.pref_role, row.pref_location or "") for row in rows]
