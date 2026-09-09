import uuid
from datetime import UTC, datetime

import pytest

from app.models.campaign import Campaign
from app.models.campaign_prospect import CampaignProspectState, CampaignProspectNextAction
from app.models.campaign_run import CampaignRun
from app.models.user import User
from app.schemas.campaign_prospect import CampaignProspectCreate, CampaignProspectUpdate
from app.schemas.discovery_shortlist import CandidateShortlistInput, DiscoveryShortlistState
from app.services.campaign_prospects import CampaignProspectError, save_campaign_prospect, update_campaign_prospect
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
