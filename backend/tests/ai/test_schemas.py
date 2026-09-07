import uuid

import pytest
from pydantic import ValidationError

from app.ai.config_loader import get_task_config, render_task_config
from app.ai.context import MAX_EVIDENCE_EXCERPT_LENGTH, build_research_evidence_context
from app.models.research_source import ResearchSource
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryTaskOutput,
    DiscoveryObjective,
    DiscoveredCompanyCandidateOutput,
    company_discovery_response_from_task_output,
)
from app.schemas.research_request import (
    KnownProspectResearchRequest,
    ResearchRequestStartRequest,
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


class TestEvidenceContext:
    def _source(self, url="https://example.com", excerpt="evidence text"):
        return ResearchSource(
            id=uuid.uuid4(),
            url=url,
            title="Example",
            source_type="web_search",
            excerpt=excerpt,
        )

    def test_context_contains_urls(self):
        context = build_research_evidence_context([self._source()])
        assert "https://example.com" in context

    def test_empty_sources_rejected(self):
        with pytest.raises(ValueError):
            build_research_evidence_context([])

    def test_excerpts_bounded(self):
        source = self._source(excerpt="x" * 5000)
        context = build_research_evidence_context([source])
        assert "x" * (MAX_EVIDENCE_EXCERPT_LENGTH + 1) not in context

    def test_source_count_bounded(self):
        sources = [self._source(url=f"https://example.com/{i}") for i in range(20)]
        context = build_research_evidence_context(sources)
        assert context.count("https://example.com/") == 12


class TestConfigLoader:
    def test_render_replaces_placeholders(self):
        config = render_task_config(
            "research_task",
            company_name="Stripe",
            evidence_context="EVIDENCE_BLOCK",
        )
        assert "Stripe" in config["description"]
        assert "EVIDENCE_BLOCK" in config["description"]
        assert "{" not in config["description"]

    def test_missing_template_value_raises(self):
        with pytest.raises(ValueError):
            render_task_config("research_task", company_name="Stripe")

    def test_unknown_task_raises(self):
        with pytest.raises(ValueError):
            get_task_config("does_not_exist")


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
            offering="Website design and online booking setup",
            desired_outcome="Decide whether this salon is worth pitching.",
            location="Lahore",
            website="https://aleezay.example",
        )
        assert request.business_name == "Aleezay Hair Beauty Care Salon"

        with pytest.raises(ValidationError):
            KnownProspectResearchRequest(
                business_name="Aleezay Hair Beauty Care Salon",
                offering="",
                desired_outcome="Decide whether this salon is worth pitching.",
            )

    def test_research_start_rejects_unsupported_objective(self):
        with pytest.raises(ValidationError, match="not supported yet"):
            ResearchRequestStartRequest(
                goal="Decide whether this business is worth pitching.",
                offering="Website redesign services",
                objective=self._objective("investment"),
            )

    def test_invalid_candidate_dropped_valid_kept(self):
        output = CompanyDiscoveryTaskOutput(
            candidates=[
                DiscoveredCompanyCandidateOutput(
                    company_name="GoodCo",
                    match_explanation="Matches fintech.",
                    supporting_source_urls=["https://goodco.com"],
                ),
                DiscoveredCompanyCandidateOutput(
                    company_name="BadCo",
                    match_explanation="Matches nothing.",
                    supporting_source_urls=["not-a-url"],
                ),
            ]
        )
        response = company_discovery_response_from_task_output(output)
        assert [c.company_name for c in response.candidates] == ["GoodCo"]
