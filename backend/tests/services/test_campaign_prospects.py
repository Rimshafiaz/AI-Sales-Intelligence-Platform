import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import event

from app.models.campaign import Campaign
from app.models.campaign_prospect import (
    CampaignProspect,
    CampaignProspectNextAction,
    CampaignProspectState,
)
from app.models.campaign_run import CampaignRun
from app.models.user import User
from app.schemas.campaign_prospect import CampaignProspectCreate, CampaignProspectUpdate
from app.schemas.discovery_shortlist import CandidateShortlistInput, DiscoveryShortlistState
from app.services.campaign_prospects import (
    CampaignProspectError,
    list_campaign_prospects_for_user,
    save_campaign_prospect,
    update_campaign_prospect,
)
from app.services.campaigns import list_campaign_summaries_for_user
from tests.services.test_campaigns import candidate, shortlist_entry


NOW = datetime(2026, 9, 9, tzinfo=UTC)


class FakeSession:
    def __init__(self, scalar_results=None, commit_error=None):
        self.scalar_results = list(scalar_results or [])
        self.commit_error = commit_error
        self.added = []
        self.committed = False

    def scalar(self, statement):
        return self.scalar_results.pop(0)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.committed = True

    def refresh(self, value):
        if hasattr(value, "created_at"):
            value.created_at = value.created_at or NOW
        if hasattr(value, "updated_at"):
            value.updated_at = value.updated_at or NOW

    def rollback(self):
        pass


def request(state=DiscoveryShortlistState.ELIGIBLE_FOR_DEEPER_RESEARCH):
    entry = shortlist_entry(state)
    return CampaignProspectCreate(
        campaign_run_id=uuid.uuid4(),
        candidate_input=CandidateShortlistInput(candidate=candidate()),
        shortlist_entry=entry,
    )


def campaign_run() -> CampaignRun:
    return CampaignRun(id=uuid.uuid4(), campaign_id=uuid.uuid4())


def campaign(run: CampaignRun) -> Campaign:
    return Campaign(id=run.campaign_id, user_id=uuid.uuid4(), title="Test", discovery_criteria={}, model_selection={})


class TestCampaignProspectSchema:
    def test_excludes_are_not_saveable(self):
        with pytest.raises(ValueError, match="Excluded candidates"):
            request(DiscoveryShortlistState.EXCLUDED)


class TestCampaignProspectService:
    def test_saves_owner_scoped_snapshot_with_next_action(self):
        run = campaign_run()
        campaign_record = campaign(run)
        owner = User(id=campaign_record.user_id, email="owner@example.com")
        db = FakeSession(scalar_results=[campaign_record, run, None])
        saved = save_campaign_prospect(db, campaign_record.id, owner, request())

        assert db.committed is True
        assert saved.campaign_id == campaign_record.id
        assert saved.source_identity_key == "open_places:overture:glow-salon"
        assert saved.workflow_state is CampaignProspectState.SAVED
        assert saved.next_action is CampaignProspectNextAction.RESEARCH_PROSPECT
        assert saved.candidate_snapshot["company_name"] == "Glow Salon"

    def test_rejects_duplicate_candidate_in_same_campaign(self):
        run = campaign_run()
        campaign_record = campaign(run)
        owner = User(id=campaign_record.user_id, email="owner@example.com")
        db = FakeSession(scalar_results=[campaign_record, run, object()])

        with pytest.raises(CampaignProspectError, match="already saved"):
            save_campaign_prospect(db, campaign_record.id, owner, request())

        assert db.added == []
        assert db.committed is False

    def test_rejects_run_from_another_campaign(self):
        run = campaign_run()
        campaign_record = campaign(run)
        owner = User(id=campaign_record.user_id, email="owner@example.com")
        db = FakeSession(scalar_results=[campaign_record, None])

        with pytest.raises(CampaignProspectError, match="does not belong"):
            save_campaign_prospect(db, campaign_record.id, owner, request())

    def test_state_update_recalculates_next_action(self):
        run = campaign_run()
        campaign_record = campaign(run)
        prospect = type("Prospect", (), {
            "id": uuid.uuid4(),
            "campaign_id": campaign_record.id,
            "workflow_state": CampaignProspectState.SAVED,
            "next_action": CampaignProspectNextAction.RESEARCH_PROSPECT,
        })()
        owner = User(id=campaign_record.user_id, email="owner@example.com")
        db = FakeSession(scalar_results=[prospect])
        updated = update_campaign_prospect(
            db,
            campaign_record.id,
            prospect.id,
            owner,
            CampaignProspectUpdate(workflow_state=CampaignProspectState.READY_FOR_OUTREACH),
        )

        assert updated.workflow_state is CampaignProspectState.READY_FOR_OUTREACH
        assert updated.next_action is CampaignProspectNextAction.PREPARE_OUTREACH
        assert db.committed is True


def test_bulk_campaign_reads_are_constant_query_and_user_scoped(db):
    owner = User(id=uuid.uuid4(), email=f"owner-{uuid.uuid4().hex}@example.com")
    foreign = User(id=uuid.uuid4(), email=f"foreign-{uuid.uuid4().hex}@example.com")
    owner_campaign = Campaign(
        user_id=owner.id,
        title="Owner campaign",
        discovery_criteria={},
        model_selection={},
    )
    foreign_campaign = Campaign(
        user_id=foreign.id,
        title="Foreign campaign",
        discovery_criteria={},
        model_selection={},
    )
    db.add_all([owner, foreign, owner_campaign, foreign_campaign])
    db.flush()
    owner_run = CampaignRun(
        campaign_id=owner_campaign.id,
        criteria_snapshot={},
        model_selection_snapshot={},
        provider_summary={},
        discovered_candidate_count=2,
    )
    foreign_run = CampaignRun(
        campaign_id=foreign_campaign.id,
        criteria_snapshot={},
        model_selection_snapshot={},
        provider_summary={},
        discovered_candidate_count=1,
    )
    db.add_all([owner_run, foreign_run])
    db.flush()

    def prospect(run, campaign_record, suffix, state):
        return CampaignProspect(
            campaign_id=campaign_record.id,
            campaign_run_id=run.id,
            source_identity_key=f"provider:{suffix}",
            candidate_index=0,
            candidate_snapshot={"company_name": suffix},
            shortlist_snapshot={},
            evidence_snapshot=[],
            workflow_state=state,
        )

    owner_ready = prospect(
        owner_run, owner_campaign, "owner-ready", CampaignProspectState.READY_FOR_OUTREACH
    )
    owner_saved = prospect(
        owner_run, owner_campaign, "owner-saved", CampaignProspectState.SAVED
    )
    foreign_ready = prospect(
        foreign_run,
        foreign_campaign,
        "foreign-ready",
        CampaignProspectState.READY_FOR_OUTREACH,
    )
    db.add_all([owner_ready, owner_saved, foreign_ready])
    db.flush()
    owner_ids = {owner_ready.id, owner_saved.id}

    query_count = 0

    def count_query(*_):
        nonlocal query_count
        query_count += 1

    event.listen(db.bind, "before_cursor_execute", count_query)
    try:
        summaries = list_campaign_summaries_for_user(db, owner.id)
        all_prospects = list_campaign_prospects_for_user(db, owner)
        filtered = list_campaign_prospects_for_user(db, owner, owner_campaign.id)
        foreign_filtered = list_campaign_prospects_for_user(
            db, owner, foreign_campaign.id
        )
        summary_counts = [(saved, ready) for _, saved, ready in summaries]
        all_prospect_ids = {item.id for item in all_prospects}
        filtered_ids = {item.id for item in filtered}
    finally:
        event.remove(db.bind, "before_cursor_execute", count_query)
        db.rollback()

    assert query_count == 4
    assert summary_counts == [(2, 1)]
    assert all_prospect_ids == owner_ids
    assert filtered_ids == owner_ids
    assert foreign_filtered == []
