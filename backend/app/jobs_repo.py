import uuid
from datetime import datetime, timezone


class InMemoryJobRepository:
	def __init__(self) -> None:
		self._counter = 0
		self._jobs: dict[str, dict] = {}

	def _next_queue_position(self) -> int:
		self._counter += 1
		return self._counter

	def create_job(self, title: str | None = None) -> dict:
		job_id = str(uuid.uuid4())
		created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
		queue_position = self._next_queue_position()

		job_state = {
			"job_id": job_id,
			"status": "queued",
			"progress": 0,
			"current_step": "queued",
			"message": "Queued for processing",
			"created_at": created_at,
			"updated_at": created_at,
			"estimated_remaining_seconds": 0,
			"result": {
				"title": title or "",
				"summary": "",
				"notes_markdown": "",
				"transcript": "",
				"exports": {
					"pdf_url": "",
					"docx_url": "",
					"anki_url": "",
				},
			},
			"error": None,
		}

		self._jobs[job_id] = job_state

		return {
			"job_id": job_id,
			"queue_position": queue_position,
			"created_at": created_at,
			"job_state": job_state,
		}

	def get_job(self, job_id: str) -> dict | None:
		return self._jobs.get(job_id)

	def cancel_job(self, job_id: str) -> dict | None:
		job = self._jobs.get(job_id)
		if not job:
			return None

		job["status"] = "cancelled"
		job["current_step"] = "cancelled"
		job["message"] = "Job cancelled"
		job["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
		return job

	def retry_job(self, job_id: str) -> dict | None:
		job = self._jobs.get(job_id)
		if not job:
			return None

		job["status"] = "queued"
		job["current_step"] = "queued"
		job["message"] = "Queued for processing"
		job["progress"] = 0
		job["error"] = None
		job["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
		return job

	def list_jobs(self) -> list[dict]:
		return list(self._jobs.values())
