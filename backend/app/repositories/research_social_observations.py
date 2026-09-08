from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.social_enrichment import social_profile_key
from app.models.research_request import ResearchRequest
from app.models.research_social_observation import ResearchSocialObservation
from app.schemas.social_enrichment import SocialProfileObservation


def upsert_social_observation(
    db: Session,
    research_request_id: UUID,
    observation: SocialProfileObservation,
) -> ResearchSocialObservation:
    profile_url = str(observation.profile_url).rstrip("/")
    profile_identity_key = social_profile_key(profile_url) or profile_url.casefold()
    statement = select(ResearchSocialObservation).where(
        ResearchSocialObservation.research_request_id == research_request_id,
        ResearchSocialObservation.profile_identity_key == profile_identity_key,
    )
    record = db.scalar(statement)
    values = {
        "platform": observation.platform.value,
        "profile_url": profile_url,
        "state": observation.state.value,
        "detail": observation.detail,
        "display_name": observation.display_name,
        "handle": observation.handle,
        "external_url": str(observation.external_url).rstrip("/") if observation.external_url else None,
        "provider_profile_id": observation.provider_profile_id,
        "is_private": observation.is_private,
        "latest_public_post_at": observation.latest_public_post_at,
        "recent_public_post_dates": [
            value.isoformat() for value in observation.recent_public_post_dates
        ],
        "source_provider": observation.source.provider,
        "source_record_id": observation.source.provider_record_id,
        "source_url": str(observation.source.source_url).rstrip("/"),
        "retrieved_at": observation.source.retrieved_at,
    }
    if record is None:
        record = ResearchSocialObservation(
            research_request_id=research_request_id,
            profile_identity_key=profile_identity_key,
            **values,
        )
        db.add(record)
        return record

    for field, value in values.items():
        setattr(record, field, value)
    return record


def list_social_observations_for_user(
    db: Session,
    research_request_id: UUID,
    user_id: UUID,
) -> list[ResearchSocialObservation]:
    statement = (
        select(ResearchSocialObservation)
        .join(
            ResearchRequest,
            ResearchSocialObservation.research_request_id == ResearchRequest.id,
        )
        .where(
            ResearchSocialObservation.research_request_id == research_request_id,
            ResearchRequest.user_id == user_id,
        )
        .order_by(ResearchSocialObservation.retrieved_at.desc())
    )
    return list(db.scalars(statement))
