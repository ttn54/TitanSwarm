"""
Tests for multi-tenant auth: user creation, login, per-user ledger, and
job/profile isolation between different users.
"""
import pytest
import pytest_asyncio
from src.infrastructure.postgres_repo import PostgresRepository


@pytest_asyncio.fixture
async def repo():
    r = PostgresRepository("sqlite+aiosqlite:///:memory:")
    await r.init_db()
    yield r
    await r.close()


# ── User creation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_returns_id(repo):
    """create_user must return a positive integer user_id."""
    user_id = await repo.create_user("alice", "secret123")
    assert isinstance(user_id, int)
    assert user_id > 0


@pytest.mark.asyncio
async def test_create_duplicate_username_raises(repo):
    """Registering the same username twice must raise ValueError."""
    await repo.create_user("alice", "secret123")
    with pytest.raises(ValueError, match="already exists"):
        await repo.create_user("alice", "different_password")


@pytest.mark.asyncio
async def test_password_is_hashed_not_stored_plaintext(repo):
    """The stored password hash must NOT equal the plaintext password."""
    await repo.create_user("alice", "secret123")
    user = await repo.get_user_by_username("alice")
    assert user is not None
    assert user["password_hash"] != "secret123"


# ── Login / verify ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_correct_password_returns_user_id(repo):
    """verify_user with correct password must return the user_id."""
    uid = await repo.create_user("alice", "secret123")
    result = await repo.verify_user("alice", "secret123")
    assert result == uid


@pytest.mark.asyncio
async def test_verify_wrong_password_returns_none(repo):
    """verify_user with wrong password must return None."""
    await repo.create_user("alice", "secret123")
    result = await repo.verify_user("alice", "wrongpassword")
    assert result is None


@pytest.mark.asyncio
async def test_verify_unknown_username_returns_none(repo):
    """verify_user for a non-existent user must return None."""
    result = await repo.verify_user("nobody", "whatever")
    assert result is None


# ── Per-user ledger ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_get_ledger(repo):
    """save_ledger / get_ledger must persist and retrieve per-user content."""
    uid = await repo.create_user("alice", "pw")
    await repo.save_ledger(uid, "## Skills\n* Python")
    content = await repo.get_ledger(uid)
    assert content == "## Skills\n* Python"


@pytest.mark.asyncio
async def test_ledger_isolated_between_users(repo):
    """Two users must not see each other's ledger content."""
    uid_a = await repo.create_user("alice", "pw")
    uid_b = await repo.create_user("bob", "pw")
    await repo.save_ledger(uid_a, "Alice's resume")
    await repo.save_ledger(uid_b, "Bob's resume")
    assert await repo.get_ledger(uid_a) == "Alice's resume"
    assert await repo.get_ledger(uid_b) == "Bob's resume"


@pytest.mark.asyncio
async def test_get_ledger_returns_empty_string_for_new_user(repo):
    """get_ledger for a user who hasn't saved anything must return ''."""
    uid = await repo.create_user("alice", "pw")
    content = await repo.get_ledger(uid)
    assert content == ""


# ── Job isolation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jobs_isolated_between_users(repo):
    """User A's jobs must not appear when fetching user B's jobs."""
    from src.core.models import Job, JobStatus
    uid_a = await repo.create_user("alice", "pw")
    uid_b = await repo.create_user("bob", "pw")

    job = Job(
        id="job-1",
        company="Acme",
        role="SWE",
        status=JobStatus.DISCOVERED,
        job_description="Python dev",
        required_skills=[],
        custom_questions=[],
        url="https://acme.com/job-1",
    )
    await repo.save_job(job, user_id=uid_a)

    # Bob should see no jobs
    bob_jobs = await repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=uid_b)
    assert len(bob_jobs) == 0

    # Alice should see her job
    alice_jobs = await repo.get_jobs_by_status(JobStatus.DISCOVERED, user_id=uid_a)
    assert len(alice_jobs) == 1


@pytest.mark.asyncio
async def test_default_user_id_1_backward_compatible(repo):
    """Calls without user_id must default to user_id=1 (backward compat for existing data)."""
    from src.core.models import Job, JobStatus
    # Seed user id=1
    await repo.create_user("default", "pw")

    job = Job(
        id="job-default",
        company="Corp",
        role="Dev",
        status=JobStatus.DISCOVERED,
        job_description="desc",
        required_skills=[],
        custom_questions=[],
        url="https://corp.com",
    )
    await repo.save_job(job)  # no user_id — should default to 1
    jobs = await repo.get_jobs_by_status(JobStatus.DISCOVERED)  # also defaults to 1
    assert any(j.id == "job-default" for j in jobs)
