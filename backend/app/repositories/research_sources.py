from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.search_provider import CollectedSource
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
