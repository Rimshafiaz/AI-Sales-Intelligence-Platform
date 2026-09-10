import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.campaign import Campaign
from app.models.campaign_prospect import CampaignProspect, CampaignProspectState
from app.models.campaign_run import CampaignRun
from app.models.research_request import ResearchStatus
from app.models.user import User
from app.schemas.campaign import (
    CampaignCandidateSelectionCreate,
    CampaignCreate,
    CampaignRecommendedBatchCreate,
    CampaignRunCreate,
)
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    DiscoveredCompanyCandidate,
)
from app.schemas.discovery_shortlist import (
    CandidateShortlistInput,
    CandidateShortlistEntry,
    DiscoveryOpportunityQueueEntry,
    DiscoveryOpportunityReason,
    PreparedDiscoveryOpportunity,
    DiscoveryShortlistState,
    NextEvidenceAction,
    OpportunityModelShortlistEvaluation,
)
from app.schemas.opportunity_models import (
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    OpportunityModelSelection,
)
from app.services.campaigns import (
    CampaignWorkflowError,
    create_candidate_selection_and_research_request,
    create_recommended_research_batch,
)


NOW = datetime(2026, 9, 8, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results=None, commit_error=None, scalars_all_results=None):
        self.scalar_results = list(scalar_results or [])
        self.scalars_all_results = list(scalars_all_results or [])
        self.commit_error = commit_error
        self.added = []
        self.committed = False
        self.rolled_back = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    class _Scalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    def scalars(self, statement):
        return FakeSession._Scalars(self.scalars_all_results.pop(0) if self.scalars_all_results else [])

    def add(self, value):
        self.added.append(value)

    def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True

    def refresh(self, value):
        if value.created_at is None:
            value.created_at = NOW
        if hasattr(value, "updated_at") and value.updated_at is None:
            value.updated_at = NOW

    def rollback(self):
        self.rolled_back = True


def criteria() -> CompanyDiscoveryRequest:
    return CompanyDiscoveryRequest(
        offering="Website redesign",
        desired_outcome="Find prospects for deeper research.",
        business_category="Beauty salons",
        location="Lahore",
    )


def model_selection(confirmed=True) -> OpportunityModelSelection:
    return OpportunityModelSelection(
        model_ids=("web_conversion.no_verified_web_presence",),
        confirmed_by_user=confirmed,
    )


def candidate() -> DiscoveredCompanyCandidate:
    return DiscoveredCompanyCandidate(
        company_name="Glow Salon",
        industry="beauty_salon",
        match_explanation="A local discovery source returned this candidate.",
        source_provider="open_places",
        source_record_id="overture:glow-salon",
        source_retrieved_at=NOW,
        discovery_source_types=["local_places"],
    )


def shortlist_entry(state=DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH):
    return CandidateShortlistEntry(
        candidate_index=0,
        company_name="Glow Salon",
        state=state,
        model_evaluations=[
            OpportunityModelShortlistEvaluation(
                model_id="web_conversion.no_verified_web_presence",
                state=state,
                reason="A cautious shortlist decision.",
                next_evidence_action=NextEvidenceAction.NO_ACTION,
            )
        ],
        next_evidence_action=NextEvidenceAction.NO_ACTION,
    )


def selection_data() -> CampaignCandidateSelectionCreate:
    evidence = EvidenceSignal(
        signal_type=EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value="The official site confirms the business identity.",
        source=EvidenceSource(
            provider="official_website",
            source_url="https://glowsalon.example",
            retrieved_at=NOW,
        ),
        captured_at=NOW,
    )
    return CampaignCandidateSelectionCreate(
        candidate_input=CandidateShortlistInput(
            candidate=candidate(),
            evidence_signals=[evidence],
        ),
        shortlist_entry=shortlist_entry(),
    )


def prepared_opportunity(name: str = "Glow Salon"):
    candidate_input = CandidateShortlistInput(
        candidate=candidate().model_copy(
            update={
                "company_name": name,
                "source_record_id": f"overture:{name.casefold().replace(' ', '-')}",
            }
        ),
        evidence_signals=[
            EvidenceSignal(
                signal_type=EvidenceSignalType.BUSINESS_IDENTITY_CONFIRMED,
                evidence_type=EvidenceType.OBSERVED,
                supporting_value="A stable local source identifies this business.",
                source=EvidenceSource(
                    provider="open_places",
                    provider_record_id=f"overture:{name.casefold().replace(' ', '-')}",
                    retrieved_at=NOW,
                ),
                captured_at=NOW,
            )
        ],
    )
    shortlist = shortlist_entry().model_copy(update={"company_name": name})
    queue_entry = DiscoveryOpportunityQueueEntry(
        candidate_index=0,
        company_name=name,
        reasons=[
            DiscoveryOpportunityReason(
                model_id="web_conversion.no_verified_web_presence",
                signal_type=EvidenceSignalType.NO_LISTED_OFFICIAL_WEBSITE,
                supporting_value="The discovery record did not list an official website.",
                source=EvidenceSource(
                    provider="open_places",
                    provider_record_id=f"overture:{name.casefold().replace(' ', '-')}",
                    retrieved_at=NOW,
                ),
                captured_at=NOW,
            )
        ],
    )
    return PreparedDiscoveryOpportunity(
        queue_entry=queue_entry,
        candidate_input=candidate_input,
        shortlist_entry=shortlist,
    )


def campaign_run() -> CampaignRun:
    campaign_id = uuid.uuid4()
    return CampaignRun(
        id=uuid.uuid4(),
        campaign_id=campaign_id,
        criteria_snapshot=criteria().model_dump(mode="json"),
        model_selection_snapshot=model_selection().model_dump(mode="json"),
        provider_summary={"open_places": 10},
        discovered_candidate_count=10,
    )


class TestCampaignSchemas:
    def test_campaign_rejects_a_blank_title(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                title="   ",
                criteria=criteria(),
                model_selection=model_selection(),
            )

    def test_campaign_requires_confirmed_model_selection(self):
        with pytest.raises(ValidationError, match="Confirm the Opportunity Model"):
            CampaignCreate(
                title="Lahore salon website prospects",
                criteria=criteria(),
                model_selection=model_selection(confirmed=False),
            )

    def test_run_summary_cannot_be_smaller_than_deduplicated_result_count(self):
        with pytest.raises(ValidationError, match="Provider counts"):
            CampaignRunCreate(
                provider_summary={"open_places": 2},
                discovered_candidate_count=3,
            )

    def test_selection_requires_candidate_eligible_for_deeper_research(self):
        with pytest.raises(ValidationError, match="eligible for deeper research"):
            CampaignCandidateSelectionCreate(
                candidate_input=CandidateShortlistInput(candidate=candidate()),
                shortlist_entry=shortlist_entry(DiscoveryShortlistState.NEEDS_EVIDENCE),
            )


class TestCampaignSelectionHandoff:
    def test_persists_only_selected_snapshot_and_creates_pending_research_request(self):
        db = FakeSession(scalar_results=[None, None, None])
        user = User(id=uuid.uuid4(), email="owner@example.com")

        selection, research_request = create_candidate_selection_and_research_request(
            db,
            campaign_run(),
            user,
            selection_data(),
        )

        assert db.committed is True
        assert selection.source_identity_key == "open_places:overture:glow-salon"
        assert selection.candidate_snapshot["company_name"] == "Glow Salon"
        assert len(selection.evidence_snapshot) == 1
        assert research_request.status is ResearchStatus.PENDING
        assert research_request.started_at is None
        assert research_request.finished_at is None
        assert research_request.objective["business_name"] == "Glow Salon"
        assert research_request.objective["campaign_run_id"] == str(selection.campaign_run_id)

    def test_rejects_duplicate_selection_without_creating_new_records(self):
        existing_selection = object()
        db = FakeSession(scalar_results=[existing_selection])
        user = User(id=uuid.uuid4(), email="owner@example.com")

        with pytest.raises(CampaignWorkflowError, match="already been selected"):
            create_candidate_selection_and_research_request(
                db,
                campaign_run(),
                user,
                selection_data(),
            )

        assert db.added == []
        assert db.committed is False

    def test_rolls_back_if_the_atomic_handoff_cannot_be_committed(self):
        db = FakeSession(scalar_results=[None, None, None], commit_error=RuntimeError("db down"))
        user = User(id=uuid.uuid4(), email="owner@example.com")

        with pytest.raises(RuntimeError, match="db down"):
            create_candidate_selection_and_research_request(
                db,
                campaign_run(),
                user,
                selection_data(),
            )

        assert db.rolled_back is True

    def test_recommended_batch_creates_multiple_pending_requests_in_one_commit(self):
        db = FakeSession(scalar_results=[None, None, None, None, None, None])
        user = User(id=uuid.uuid4(), email="owner@example.com")
        batch = CampaignRecommendedBatchCreate(
            opportunities=[prepared_opportunity("Glow Salon"), prepared_opportunity("Lumen Salon")]
        )

        selections = create_recommended_research_batch(db, campaign_run(), user, batch)

        assert len(selections) == 2
        assert db.committed is True
        assert all(request.status is ResearchStatus.PENDING for _, request in selections)

    def test_recommended_batch_rejects_an_opportunity_outside_the_campaign_models(self):
        db = FakeSession()
        user = User(id=uuid.uuid4(), email="owner@example.com")
        opportunity = prepared_opportunity()
        opportunity.queue_entry.reasons[0].model_id = "web_conversion.mobile_performance"
        batch = CampaignRecommendedBatchCreate(opportunities=[opportunity])

        with pytest.raises(CampaignWorkflowError, match="does not match"):
            create_recommended_research_batch(db, campaign_run(), user, batch)

        assert db.added == []


def test_recommended_batch_rejects_prospects_already_ruled_out():
    run = campaign_run()
    ruled_out_key = (
        f"{prepared_opportunity('Glow Salon').candidate_input.candidate.source_provider}:"
        f"{prepared_opportunity('Glow Salon').candidate_input.candidate.source_record_id}"
    )
    not_a_fit_prospect = CampaignProspect(
        campaign_id=run.campaign_id,
        campaign_run_id=run.id,
        source_identity_key=ruled_out_key,
        candidate_index=0,
        candidate_snapshot={},
        shortlist_snapshot={},
        evidence_snapshot=[],
        workflow_state=CampaignProspectState.NOT_A_FIT,
    )
    db = FakeSession(scalars_all_results=[[not_a_fit_prospect]])
    user = User(id=uuid.uuid4(), email="owner@example.com")
    batch = CampaignRecommendedBatchCreate(
        opportunities=[prepared_opportunity("Glow Salon")]
    )

    with pytest.raises(CampaignWorkflowError, match="ruled out"):
        create_recommended_research_batch(db, run, user, batch)
    assert db.committed is False
