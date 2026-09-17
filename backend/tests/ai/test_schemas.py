import pytest
from pydantic import ValidationError

from app.ai.config_loader import get_task_config, render_task_config
from app.ai.tasks.goal_parser_task import create_goal_parser_task
from app.schemas.agent_outputs import (
    BriefReviewOutput,
    OpportunityOutreachOutput,
    SocialResearchOutput,
    WebsiteResearchOutput,
)
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    DiscoveryObjective,
    ParseDiscoveryRequest,
)
from app.schemas.research_request import (
    KnownProspectResearchRequest,
)
from app.schemas.sales_intelligence_report import SalesIntelligenceReport

from tests.conftest import make_valid_report_data


class TestReportSchemaValidation:
    def test_valid_report_accepted(self):
        report = SalesIntelligenceReport.model_validate(make_valid_report_data())
        assert report.opportunity_assessment.score == 72

    def test_score_out_of_range_rejected(self):
        data = make_valid_report_data(score=101)
        with pytest.raises(ValidationError):
            SalesIntelligenceReport.model_validate(data)

    def test_finding_without_citations_rejected(self):
        data = make_valid_report_data()
        data["executive_summary"]["citations"] = []
        with pytest.raises(ValidationError):
            SalesIntelligenceReport.model_validate(data)

    def test_blank_statement_rejected(self):
        data = make_valid_report_data()
        data["executive_summary"]["statement"] = "   "
        with pytest.raises(ValidationError):
            SalesIntelligenceReport.model_validate(data)

    def test_unlabeled_inference_rejected(self):
        data = make_valid_report_data()
        data["strategy"]["recommended_strategy"]["is_inference"] = False
        with pytest.raises(ValidationError):
            SalesIntelligenceReport.model_validate(data)


class TestProspectEvidenceBriefAgentOutputs:
    finding = {
        "statement": "Mobile performance was measured at 31/100.",
        "claim_kind": "derived_metric",
        "evidence_keys": ["research_evidence:mobile-score"],
    }

    def test_distinct_investigation_contracts(self):
        website = WebsiteResearchOutput(website_status="verified", findings=[self.finding])
        social = SocialResearchOutput(
            presence_status="partially_verified",
            findings=[self.finding],
        )
        assert website.website_status == "verified"
        assert social.presence_status == "partially_verified"

    def test_outreach_requires_pitch_angle_and_personalization_basis(self):
        payload = {
            "opportunity_summary": self.finding,
            "pitch_angle": {
                "statement": "A mobile-focused booking improvement may be relevant.",
                "offering": "Website redesign and booking setup",
                "evidence_keys": ["research_evidence:mobile-score"],
            },
            "personalization_basis": [self.finding],
        }
        assert OpportunityOutreachOutput.model_validate(payload).pitch_angle.offering

        with pytest.raises(ValidationError):
            OpportunityOutreachOutput.model_validate(payload | {"personalization_basis": []})
        with pytest.raises(ValidationError):
            OpportunityOutreachOutput.model_validate(
                {key: value for key, value in payload.items() if key != "pitch_angle"}
            )

    def test_review_issues_are_structured(self):
        review = BriefReviewOutput(
            approved=False,
            issues=[
                {
                    "issue_type": "generic_outreach",
                    "reason": "Message lacks specificity.",
                }
            ],
        )
        assert review.issues[0].issue_type == "generic_outreach"

class TestConfigLoader:
    def test_render_replaces_placeholders(self):
        config = render_task_config(
            "goal_parser_task",
            goal_context="Find dental clinics in Toronto",
            hint_context="None provided.",
        )
        assert "Find dental clinics in Toronto" in config["description"]
        assert "{" not in config["description"]

    def test_missing_template_value_raises(self):
        with pytest.raises(ValueError):
            render_task_config("goal_parser_task", goal_context="Find clinics")

    def test_unknown_task_raises(self):
        with pytest.raises(ValueError):
            get_task_config("does_not_exist")

    def test_goal_parser_is_toolless_and_uses_narrow_agent(self):
        task = create_goal_parser_task(
            ParseDiscoveryRequest(goal="Find dental clinics that need website work")
        )
        assert task.tools == []
        assert task.agent.tools == []
        assert task.agent.role.strip() == "Seller Goal Parser"


class TestDiscoverySchemas:
    def _objective(self, goal_type: str = "service_pitch") -> DiscoveryObjective:
        return DiscoveryObjective(
            goal_type=goal_type,
            offering="Website redesign services",
            target_sectors=["Dental clinics"],
            target_geographies=["Toronto"],
            search_queries=["dental clinics Toronto", "Toronto dentists"],
            fit_rubric="Look for local clinics with measurable website gaps.",
            desired_outcome="Decide which clinics are worth pitching.",
        )

    def test_local_discovery_requires_all_core_fields(self):
        with pytest.raises(ValidationError):
            CompanyDiscoveryRequest()

    def test_valid_local_discovery_input_is_normalized(self):
        criteria = CompanyDiscoveryRequest(
            offering="  Website redesign services  ",
            desired_outcome="  Decide which businesses are worth pitching.  ",
            business_category="  Dental clinics  ",
            location="  Toronto  ",
        )
        assert criteria.offering == "Website redesign services"
        assert criteria.industry == "Dental clinics"
        assert criteria.region == "Toronto"

    def test_supported_objective_can_supply_required_discovery_fields(self):
        criteria = CompanyDiscoveryRequest(objective=self._objective())
        assert criteria.goal_type == "service_pitch"
        assert criteria.offering == "Website redesign services"
        assert criteria.business_category == "Dental clinics"
        assert criteria.location == "Toronto"

    def test_unsupported_discovery_objective_is_rejected(self):
        with pytest.raises(ValidationError, match="not supported yet"):
            CompanyDiscoveryRequest(objective=self._objective("hiring"))

    def test_known_prospect_requires_scope_and_validates_website(self):
        request = KnownProspectResearchRequest(
            business_name="  Aleezay Hair Beauty Care Salon  ",
            goal="Decide whether the salon is worth pitching for a better booking website.",
            offering="Website design and online booking setup",
            desired_outcome="Decide whether this salon is worth pitching.",
            location="Lahore",
            website="https://aleezay.example",
            phone_number="  +92 300 1234567  ",
        )
        assert request.business_name == "Aleezay Hair Beauty Care Salon"
        assert request.phone_number == "+92 300 1234567"

        with pytest.raises(ValidationError):
            KnownProspectResearchRequest(
                business_name="Aleezay Hair Beauty Care Salon",
                goal="Decide whether this salon is worth pitching.",
                offering="",
                desired_outcome="Decide whether this salon is worth pitching.",
            )
