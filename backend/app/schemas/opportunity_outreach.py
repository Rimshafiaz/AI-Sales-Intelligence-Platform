from pydantic import BaseModel, ConfigDict

from app.schemas.agent_outputs import SocialResearchOutput, WebsiteResearchOutput
from app.schemas.prospect_evidence_brief import (
    BriefEvidence,
    BriefObjective,
    BriefProspect,
    BriefQualification,
    OutreachChannel,
)
from app.services.aggregate_verdict import AggregateVerdict


class OpportunityOutreachHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: BriefObjective
    prospect: BriefProspect
    aggregate_verdict: AggregateVerdict
    qualifications: list[BriefQualification]
    website_research: WebsiteResearchOutput | None = None
    social_research: SocialResearchOutput | None = None
    evidence: list[BriefEvidence]
    available_verified_channels: list[OutreachChannel]
