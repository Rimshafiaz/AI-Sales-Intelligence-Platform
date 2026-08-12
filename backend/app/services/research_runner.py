from uuid import UUID

from app.db.session import SessionLocal
from app.repositories.research_requests import (
    mark_research_request_complete,
    mark_research_request_failed,
    mark_research_request_running,
)


def run_development_research(
    request_id: UUID,
    simulate_failure: bool = False,
) -> None:
    db = SessionLocal()

    try:
        research_request = mark_research_request_running(
            db,
            request_id,
        )

        if research_request is None:
            return

        if simulate_failure:
            raise RuntimeError("Development failure")

        mark_research_request_complete(
            db,
            request_id,
        )

    except Exception:
        db.rollback()
        mark_research_request_failed(
            db,
            request_id,
            "Development research runner failed.",
        )

    finally:
        db.close()
