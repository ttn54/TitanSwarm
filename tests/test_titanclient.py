import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.models import Job, JobStatus
from src.infrastructure.titanstore import TitanStoreClient

@pytest.fixture
def sample_job():
    return Job(
        id="hash-1234",
        company="TechCorp",
        role="SWE",
        job_description="Description",
        url="https://example.com"
    )

@pytest.mark.asyncio
async def test_save_job_success(sample_job):
    client = TitanStoreClient("localhost", 6001)
    
    # Mocking _send_command to avoid actual network calls in tests
    client._send_command = AsyncMock(return_value="OK")
    
    success = await client.save_job(sample_job)
    
    assert success is True
    client._send_command.assert_called_once()
    
    # Check if the command was formatted correctly
    sent_command = client._send_command.call_args[0][0]
    assert sent_command.startswith("SET job:hash-1234 ")
    assert "TechCorp" in sent_command

@pytest.mark.asyncio
async def test_get_job_success(sample_job):
    client = TitanStoreClient("localhost", 6001)
    
    mock_json = sample_job.model_dump_json()
    client._send_command = AsyncMock(return_value=f"VALUE {mock_json}")
    
    job = await client.get_job("hash-1234")
    
    assert job is not None
    assert job.id == "hash-1234"
    assert job.company == "TechCorp"
    client._send_command.assert_called_once_with("GET job:hash-1234\n")

@pytest.mark.asyncio
@patch("src.infrastructure.titanstore.asyncio.open_connection")
async def test_leader_redirect(mock_open_connection, sample_job):
    """Test that the client reconnects when it receives a NOT_LEADER error."""
    client = TitanStoreClient("localhost", 5000)
    
    # Mock stream reader and writer
    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()
    
    # First time, send NOT_LEADER, second time, send OK
    mock_reader.readuntil = AsyncMock(side_effect=[
        b"ERR NOT_LEADER localhost:6002\n",
        b"OK\n"
    ])
    
    mock_open_connection.return_value = (mock_reader, mock_writer)
    
    success = await client.save_job(sample_job)
    
    assert success is True
    # The client should have updated its host and port
    assert client.host == "localhost"
    assert client.port == 6002
    # Connection should have been established twice
    assert mock_open_connection.call_count == 2
