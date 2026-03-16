from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
from pathlib import Path

SCHEDULE_FILE = Path("schedule.json")
scheduler = BackgroundScheduler()
scheduler.start()


def _load_jobs() -> list:
    if SCHEDULE_FILE.exists():
        return json.loads(SCHEDULE_FILE.read_text())
    return []


def _save_jobs(jobs: list):
    SCHEDULE_FILE.write_text(json.dumps(jobs, ensure_ascii=False, indent=2))


def schedule_post(job_id: str, run_at: datetime, platforms: list, text: str, media_path: str = None):
    from main import execute_post

    def job():
        execute_post(platforms, text, media_path)
        jobs = [j for j in _load_jobs() if j["id"] != job_id]
        _save_jobs(jobs)

    scheduler.add_job(job, "date", run_date=run_at, id=job_id)
    jobs = _load_jobs()
    jobs.append({
        "id": job_id,
        "run_at": run_at.isoformat(),
        "platforms": platforms,
        "text": text[:100],
        "status": "pending",
    })
    _save_jobs(jobs)


def cancel_job(job_id: str) -> bool:
    try:
        scheduler.remove_job(job_id)
        _save_jobs([j for j in _load_jobs() if j["id"] != job_id])
        return True
    except Exception:
        return False


def list_jobs() -> list:
    return _load_jobs()
