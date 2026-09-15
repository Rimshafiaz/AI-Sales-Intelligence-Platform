import uuid

import pytest
from pydantic import ValidationError

from app.models.research_request import ResearchRequest
from app.schemas.agent_outputs import WebsiteResearchOutput
from app.schemas.opportunity_models import OpportunityModelSelection
from app.services.website_research import persist_website_research_output


class FakeSession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        return value


def research_request():
    return ResearchRequest(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )


def website_output():
    return WebsiteResearchOutput(
        website_status="verified",
        findings=[
            {
                "statement": "The verified site has measured mobile evidence.",
                "claim_kind": "observed",
                "evidence_keys": ["evidence:mobile"],
            }
        ],
        evidence_gaps=[],
        caveats=[],
    )


def test_valid_website_output_is_validated_and_namespaced_without_overwriting_social():
    request = research_request()
    request.specialist_outputs = {"social": {"presence_status": "verified"}}
    db = FakeSession()

    persist_website_research_output(db, request, request.user_id, website_output())

    assert request.specialist_outputs["website"]["website_status"] == "verified"
    assert request.specialist_outputs["social"] == {"presence_status": "verified"}
    assert db.commits == 1


def test_invalid_website_output_is_rejected_before_persistence():
    request = research_request()
    db = FakeSession()

    with pytest.raises(ValidationError):
        persist_website_research_output(
            db,
            request,
            request.user_id,
            {"website_status": "qualified", "findings": []},
        )

    assert request.specialist_outputs is None
    assert db.commits == 0


def test_request_model_scope_round_trips_through_canonical_contract():
    request = research_request()
    selection = OpportunityModelSelection(
        model_ids=("web_conversion.mobile_performance",),
        confirmed_by_user=True,
    )
    request.opportunity_model_selection = selection.model_dump(mode="json")

    assert OpportunityModelSelection.model_validate(
        request.opportunity_model_selection
    ) == selection
