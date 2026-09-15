from sqlalchemy.orm import Session

from app.ai.website_research import WebsiteResearchError, run_website_research_agent
from app.ai.social_research import SocialResearchError, run_social_research_agent
from app.ai.tools.social_research import build_grounded_social_evidence
from app.models.campaign_candidate_selection import CampaignCandidateSelection
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.opportunity_models import OpportunityModelSelection, ServiceFamily
from app.schemas.opportunity_qualification import OpportunityQualificationRunRequest
from app.services.opportunity_model_catalog import get_opportunity_model
from app.services.opportunity_qualification import (
    OpportunityQualificationError,
    QualificationDecision,
    qualify_research_request,
)
from app.services.website_research import persist_website_research_output
from app.services.social_research import persist_social_research_output


def research_then_qualify(
    db: Session,
    research_request: ResearchRequest,
    company: Company,
    selection: CampaignCandidateSelection | None,
    request: OpportunityQualificationRunRequest,
) -> list[QualificationDecision]:
    try:
        model_selection = OpportunityModelSelection.model_validate(
            research_request.opportunity_model_selection
        )
    except ValueError as error:
        raise OpportunityQualificationError(
            "A valid persisted Opportunity Model selection is required before qualification."
        ) from error

    if any(
        get_opportunity_model(model_id).service_family is ServiceFamily.WEB_CONVERSION
        for model_id in model_selection.model_ids
    ):
        try:
            output = run_website_research_agent(
                db,
                research_request,
                company,
                selection,
                research_request.user_id,
            )
            persist_website_research_output(
                db,
                research_request,
                research_request.user_id,
                output,
            )
        except WebsiteResearchError as error:
            raise OpportunityQualificationError(str(error)) from error

    if any(
        get_opportunity_model(model_id).service_family
        is ServiceFamily.SOCIAL_PRESENCE_CONTENT
        for model_id in model_selection.model_ids
    ):
        try:
            output = run_social_research_agent(
                db,
                research_request,
                company,
                selection,
                research_request.user_id,
            )
            final_state = build_grounded_social_evidence(
                db,
                research_request,
                company,
                selection,
                research_request.user_id,
            )
            persist_social_research_output(
                db,
                research_request,
                research_request.user_id,
                output,
                {item.key for item in final_state.evidence},
            )
        except (SocialResearchError, ValueError) as error:
            raise OpportunityQualificationError(str(error)) from error

    return qualify_research_request(db, research_request, company, selection, request)
