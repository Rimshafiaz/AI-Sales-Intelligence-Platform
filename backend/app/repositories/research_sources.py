from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.search_provider import CollectedSource
from app.models.research_request import ResearchRequest
from app.models.research_source import ResearchSource
from app.schemas.evidence_gate import SourceAdmissionState
from app.services.evidence_gate import SourceAdmission


def create_research_sources(
    db: Session,
    research_request_id: UUID,
    sources: list[CollectedSource | SourceAdmission],
) -> list[ResearchSource]:
    db_sources = [
        ResearchSource(
            research_request_id=research_request_id,
            url=_source_value(source).url,
            title=_source_value(source).title,
            excerpt=_source_value(source).excerpt,
            source_type=_source_value(source).source_type,
            admission_state=(
                source.state
                if isinstance(source, SourceAdmission)
                else SourceAdmissionState.PENDING
            ),
            admission_reason=(source.reason if isinstance(source, SourceAdmission) else None),
        )
        for source in sources
    ]
    db.add_all(db_sources)
    db.commit()
    return db_sources


def _source_value(source: CollectedSource | SourceAdmission) -> CollectedSource:
    return source.source if isinstance(source, SourceAdmission) else source


def list_research_sources_for_user(
    db: Session,
    research_request_id: UUID,
    user_id: UUID,
    limit: int,
    admission_state: SourceAdmissionState | None = None,
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

    if admission_state is not None:
        statement = statement.where(ResearchSource.admission_state == admission_state)

    return db.scalars(statement).all()
