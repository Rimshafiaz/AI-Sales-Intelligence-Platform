import uuid

import pytest

from app.models.research_request import ResearchRequest
from app.services.social_research import persist_social_research_output


class FakeSession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        return value


def test_social_output_merges_without_overwriting_website():
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        specialist_outputs={"website": {"website_status": "verified"}},
    )

    persist_social_research_output(
        FakeSession(),
        request,
        request.user_id,
        {
            "presence_status": "verified",
            "findings": [{
                "statement": "The official profile was verified.",
                "claim_kind": "observed",
                "evidence_keys": ["evidence:official"],
            }],
            "evidence_gaps": [],
            "caveats": [],
        },
        {"evidence:official"},
    )

    assert request.specialist_outputs["website"] == {"website_status": "verified"}
    assert request.specialist_outputs["social"]["presence_status"] == "verified"


def test_ungrounded_social_output_is_rejected_before_persistence():
    request = ResearchRequest(
        id=uuid.uuid4(), company_id=uuid.uuid4(), user_id=uuid.uuid4()
    )

    with pytest.raises(ValueError, match="unavailable evidence"):
        persist_social_research_output(
            FakeSession(),
            request,
            request.user_id,
            {
                "presence_status": "verified",
                "findings": [{
                    "statement": "Unsupported social claim.",
                    "claim_kind": "observed",
                    "evidence_keys": ["missing:key"],
                }],
            },
            set(),
        )

    assert request.specialist_outputs is None
