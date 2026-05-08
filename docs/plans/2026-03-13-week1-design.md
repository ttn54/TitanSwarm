# Week 1 Design: The Vault & The Interface

## Architecture and Data Flow
We are establishing the foundational python models and repository boundaries for TitanSwarm so it can communicate with the custom Go database, TitanStore.
We are using the Repository Pattern to decouple our business logic from the database implementation. This allows us to easily swap out TitanStore for PostgreSQL in the future.

## Data Structures (Pydantic Models) and Interfaces
Pydantic ensures runtime type-checking and validation for Python.

```python
from enum import Enum
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    PROCESSING = "PROCESSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

class Job(BaseModel):
    id: str = Field(..., description="Unique hash of the job URL or description")
    company: str
    role: str
    status: JobStatus = JobStatus.DISCOVERED
    job_description: str
    required_skills: list[str] = Field(default_factory=list)
    custom_questions: list[str] = Field(default_factory=list)
    url: str
```

### The Repository Interface
```python
from abc import ABC, abstractmethod

class JobRepository(ABC):
    @abstractmethod
    async def save_job(self, job: Job) -> bool:
        pass
        
    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        pass
```

### The TitanStore TCP Client
```python
class TitanStoreClient(JobRepository):
    def __init__(self, host: str = "127.0.0.1", port: int = 6001):
        self.current_host = host
        self.current_port = port

    async def _send_command(self, command: str) -> str:
        # 1. Opens asyncio socket
        # 2. Sends command bytes with \n
        # 3. Reads response. 
        # 4. If "ERR NOT_LEADER <host:port>", updates current_host/port and retries.
        pass

    async def save_job(self, job: Job) -> bool:
        pass
        
    async def get_job(self, job_id: str) -> Job | None:
        pass
```

## Edge Cases and Failure Modes
- **TitanStore Follower Redirects:** If our client connects to a follower node, TitanStore replies with `ERR NOT_LEADER <new_address>`. The client must disconnect and automatically reconnect to the new address.
- **Connection Failures:** The client needs basic retries if the TCP socket refuses connection.
- **Invalid Data:** Pydantic will throw a `ValidationError` early if scrapers return incomplete data, preventing DB corruption.
