from pydantic import ConfigDict

from app.schemas.agent_outputs import SocialResearchOutput, WebsiteResearchOutput
from app.schemas.prospect_evidence_brief import ProspectEvidenceBriefContext
from app.services.aggregate_verdict import AggregateVerdict


class TrustedProspectEvidenceBriefContext(ProspectEvidenceBriefContext):
    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregate_verdict: AggregateVerdict
    website_research: WebsiteResearchOutput | None = None
    social_research: SocialResearchOutput | None = None
