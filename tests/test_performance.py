import pytest
from src.infrastructure.postgres_repo import JobModel

def test_job_model_has_indexes():
    """Verify that high-read fields on JobModel have database indexes."""
    assert JobModel.status.index == True, "status must be indexed"
    assert JobModel.user_id.index == True, "user_id must be indexed"
    assert JobModel.company.index == True, "company must be indexed"
    assert JobModel.role.index == True, "role must be indexed"

