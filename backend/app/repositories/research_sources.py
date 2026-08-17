from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.search_provider import CollectedSource
from app.models.research_request import ResearchRequest
from app.models.research_source import ResearchSource


def create_research_sources(
    db: Session,
    research_request_id: UUID,
    sources: list[CollectedSource],
) -> list[ResearchSource]:
    db_sources = [
        ResearchSource(
            research_request_id=research_request_id,
            url=source.url,
            title=source.title,
            excerpt=source.excerpt,
            source_type=source.source_type,
        )
        for source in sources
    ]
    db.add_all(db_sources)
    db.commit()
    return db_sources


def list_research_sources_for_user(
    db: Session,
    research_request_id: UUID,
    user_id: UUID,
    limit: int,
) -> list[ResearchSource]:
    statement = (
        select(ResearchSource)
        .join(
            ResearchRequest,
            ResearchSource.research_request_id == ResearchRequest.id,
        )
        .where(
            ResearchSource.research_request_id == research_request_id,
            ResearchRequest.user_id == user_id,
        )
        .order_by(ResearchSource.retrieved_at.desc())
        .limit(limit)
    )

    return db.scalars(statement).all()
