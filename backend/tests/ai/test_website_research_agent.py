import uuid
from datetime import UTC, datetime

import pytest
from crewai.tools import tool

from app.ai import website_research
from app.ai.tasks import website_research_task
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.agent_outputs import WebsiteResearchOutput
from app.schemas.opportunity_models import EvidenceSignalType, EvidenceSource, EvidenceType
from app.schemas.prospect_evidence_brief import BriefEvidence
from app.schemas.website_audit import WebsiteAuditState
from app.schemas.website_research import (
    GroundedWebsiteEvidenceResult,
    SelectedWebsiteModel,
    WebsiteTargetStatus,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)


def evidence(signal_type, key):
    return BriefEvidence(
        key=key,
        signal_type=signal_type,
        evidence_type=EvidenceType.OBSERVED,
        supporting_value="Grounded website evidence.",
        numeric_value=43.0 if signal_type is EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED else None,
        source=EvidenceSource(
            provider="test_provider",
            source_url="https://glow.example/",
            retrieved_at=NOW,
        ),
        captured_at=NOW,
    )


def state(status, required=(), available=()):
    model = SelectedWebsiteModel(
        model_id=(
            "web_conversion.mobile_performance"
            if EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED in required
            else "web_conversion.restaurant_customer_path"
        ),
        required_evidence_signals=list(required),
    )
    return GroundedWebsiteEvidenceResult(
        website_status=status,
        selected_models=[model],
        evidence=list(available),
        unresolved_requirements=[
            item for item in required if item not in {value.signal_type for value in available}
        ],
        audit_state=WebsiteAuditState.NOT_RUN,
    )


def bound_context():
    user_id = uuid.uuid4()
    company = Company(id=uuid.uuid4(), user_id=user_id, name="Glow Salon")
    request = ResearchRequest(
        id=uuid.uuid4(),
        company_id=company.id,
        user_id=user_id,
        objective={
            "goal": "Find grounded website service opportunities.",
            "offering": "Website redesign",
            "location": "Lahore",
        },
    )
    return object(), request, company, None, user_id


def fake_tools(calls):
    @tool("get_verified_website_target")
    def target() -> str:
        """Read target."""
        calls.append("target")
        return "{}"

    @tool("measure_verified_website_mobile_performance")
    def mobile() -> str:
        """Measure mobile."""
        calls.append("mobile")
        return "{}"

    @tool("inspect_verified_website_conversion_paths")
    def conversion() -> str:
        """Inspect conversion paths."""
        calls.append("conversion")
        return "{}"

    @tool("read_grounded_website_evidence")
    def read_evidence() -> str:
        """Read evidence."""
        calls.append("evidence")
        return "{}"

    return target, mobile, conversion, read_evidence


def invoke(task, name):
    return next(item for item in task.tools if item.name == name).run()


class TestWebsiteResearchAgent:
    @pytest.mark.parametrize(
        ("status", "actions"),
        [
            (WebsiteTargetStatus.NOT_VERIFIED, ["target", "evidence"]),
            (WebsiteTargetStatus.VERIFIED, ["target", "evidence", "mobile", "evidence"]),
        ],
    )
    def test_no_website_skips_checks_while_verified_mobile_can_run(
        self, monkeypatch, status, actions
    ):
        calls = []
        required = (EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,)
        final_evidence = (
            [evidence(required[0], "research_evidence:mobile")]
            if status is WebsiteTargetStatus.VERIFIED
            else []
        )
        states = iter([state(status, required), state(status, required, final_evidence)])
        monkeypatch.setattr(website_research, "build_website_research_tools", lambda *_: fake_tools(calls))
        monkeypatch.setattr(website_research, "build_grounded_website_evidence", lambda *_: next(states))

        def run(task):
            for action in actions:
                invoke(task, {
                    "target": "get_verified_website_target",
                    "evidence": "read_grounded_website_evidence",
                    "mobile": "measure_verified_website_mobile_performance",
                }[action])
            return WebsiteResearchOutput(
                website_status=status.value,
                findings=(
                    [{
                        "statement": "Mobile performance was measured at 43/100.",
                        "claim_kind": "derived_metric",
                        "evidence_keys": ["research_evidence:mobile"],
                    }]
                    if final_evidence
                    else []
                ),
                evidence_gaps=[] if final_evidence else ["No verified website permits measurement."],
            )

        monkeypatch.setattr(website_research, "_run_task", run)
        output = website_research.run_website_research_agent(*bound_context())

        assert isinstance(output, WebsiteResearchOutput)
        assert calls == actions
        assert "conversion" not in calls

    def test_conversion_and_mixed_requirements_allow_distinct_tool_choices(self, monkeypatch):
        calls = []
        required = (
            EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
            EvidenceSignalType.WEBSITE_RESTAURANT_PRIMARY_PATH_NOT_OBSERVED,
        )
        final = [
            evidence(required[0], "research_evidence:mobile"),
            evidence(required[1], "research_evidence:path"),
        ]
        states = iter([
            state(WebsiteTargetStatus.VERIFIED, required),
            state(WebsiteTargetStatus.VERIFIED, required, final),
        ])
        monkeypatch.setattr(website_research, "build_website_research_tools", lambda *_: fake_tools(calls))
        monkeypatch.setattr(website_research, "build_grounded_website_evidence", lambda *_: next(states))

        def run(task):
            for name in (
                "get_verified_website_target",
                "read_grounded_website_evidence",
                "measure_verified_website_mobile_performance",
                "inspect_verified_website_conversion_paths",
                "read_grounded_website_evidence",
            ):
                invoke(task, name)
            return WebsiteResearchOutput(
                website_status="verified",
                findings=[
                    {
                        "statement": "The verified homepage lacked the expected customer path.",
                        "claim_kind": "observed",
                        "evidence_keys": ["research_evidence:path"],
                    }
                ],
            )

        monkeypatch.setattr(website_research, "_run_task", run)
        website_research.run_website_research_agent(*bound_context())

        assert "mobile" in calls
        assert "conversion" in calls

    def test_no_gap_does_not_become_fabricated_evidence(self, monkeypatch):
        calls = []
        required = (EvidenceSignalType.WEBSITE_RESTAURANT_PRIMARY_PATH_NOT_OBSERVED,)
        states = iter([
            state(WebsiteTargetStatus.VERIFIED, required),
            state(WebsiteTargetStatus.VERIFIED, required),
        ])
        monkeypatch.setattr(website_research, "build_website_research_tools", lambda *_: fake_tools(calls))
        monkeypatch.setattr(website_research, "build_grounded_website_evidence", lambda *_: next(states))

        def run(task):
            invoke(task, "inspect_verified_website_conversion_paths")
            return WebsiteResearchOutput(
                website_status="verified",
                findings=[],
                caveats=["Inspection completed without a qualifying conversion-path gap."],
            )

        monkeypatch.setattr(website_research, "_run_task", run)
        output = website_research.run_website_research_agent(*bound_context())

        assert output.findings == []
        assert calls == ["conversion"]

    def test_unknown_evidence_key_is_rejected(self, monkeypatch):
        canonical = state(WebsiteTargetStatus.VERIFIED)
        monkeypatch.setattr(website_research, "build_website_research_tools", lambda *_: fake_tools([]))
        monkeypatch.setattr(website_research, "build_grounded_website_evidence", lambda *_: canonical)
        monkeypatch.setattr(
            website_research,
            "_run_task",
            lambda _task: WebsiteResearchOutput(
                website_status="verified",
                findings=[{
                    "statement": "Unsupported website claim.",
                    "claim_kind": "observed",
                    "evidence_keys": ["invented:key"],
                }],
            ),
        )

        with pytest.raises(website_research.WebsiteResearchError, match="unavailable evidence"):
            website_research.run_website_research_agent(*bound_context())

    def test_task_handoff_is_immutable_and_has_exactly_four_tools(self, monkeypatch):
        tools = fake_tools([])
        handoff = website_research.WebsiteResearchHandoff(
            seller_goal="Find grounded website opportunities.",
            offering="Website redesign",
            company_name="Glow Salon",
            starting_state=state(WebsiteTargetStatus.VERIFIED),
        )

        task = website_research_task.create_website_research_task(handoff, tools)
        assert '"offering": "Website redesign"' in task.description
        assert {item.name for item in task.tools} == {
            "get_verified_website_target",
            "measure_verified_website_mobile_performance",
            "inspect_verified_website_conversion_paths",
            "read_grounded_website_evidence",
        }
