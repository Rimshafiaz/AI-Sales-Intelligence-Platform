from pydantic import BaseModel, ConfigDict

from app.schemas.agent_outputs import OpportunityOutreachOutput
from app.schemas.opportunity_outreach import OpportunityOutreachHandoff


class OpportunityOutreachReviewHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context: OpportunityOutreachHandoff
    candidate: OpportunityOutreachOutput
