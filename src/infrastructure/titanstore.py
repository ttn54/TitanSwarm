import asyncio
import json
from src.core.repository import JobRepository
from src.core.models import Job

class TitanStoreClient(JobRepository):
    def __init__(self, host: str = "127.0.0.1", port: int = 6001):
        self.host = host
        self.port = port
        self.max_redirects = 5

    async def _send_command(self, command: str) -> str:
        redirects = 0
        while redirects < self.max_redirects:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                
                # Send the command
                writer.write(command.encode('utf-8'))
                await writer.drain()
                
                # Read response until newline
                response_bytes = await reader.readuntil(separator=b'\n')
                response = response_bytes.decode('utf-8').strip()
                
                writer.close()
                await writer.wait_closed()

                # Handle Leader Redirect
                if response.startswith("ERR NOT_LEADER"):
                    parts = response.split(" ")
                    if len(parts) >= 3:
                        new_address = parts[2]
                        if ":" in new_address:
                            new_host, new_port = new_address.split(":")
                            self.host = new_host
                            self.port = int(new_port)
                            redirects += 1
                            continue # Loop will retry with new host/port
                
                return response
                
            except Exception as e:
                # In a real app we'd log this and maybe do exponential backoff
                raise ConnectionError(f"Failed to communicate with TitanStore: {e}")
                
        raise ConnectionError("Exceeded maximum redirects for NOT_LEADER")

    async def save_job(self, job: Job) -> bool:
        json_payload = job.model_dump_json()
        command = f"SET job:{job.id} {json_payload}\n"
        
        response = await self._send_command(command)
        return response == "OK"

    async def get_job(self, job_id: str) -> Job | None:
        command = f"GET job:{job_id}\n"
        response = await self._send_command(command)
        
        if response == "NOT_FOUND":
            return None
            
        if response.startswith("VALUE "):
            # Extract JSON payload after "VALUE "
            json_str = response[6:]
            try:
                data = json.loads(json_str)
                return Job(**data)
            except Exception:
                return None
                
        return None
