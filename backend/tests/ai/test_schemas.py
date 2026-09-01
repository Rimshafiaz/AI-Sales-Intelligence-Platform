import uuid

import pytest
from pydantic import ValidationError

from app.ai.config_loader import get_task_config, render_task_config
from app.ai.context import MAX_EVIDENCE_EXCERPT_LENGTH, build_research_evidence_context
from app.models.research_source import ResearchSource
from app.schemas.company_discovery import (
    CompanyDiscoveryRequest,
    CompanyDiscoveryTaskOutput,
    DiscoveredCompanyCandidateOutput,
    company_discovery_response_from_task_output,
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
    def test_at_least_one_criterion_required(self):
        with pytest.raises(ValidationError):
            CompanyDiscoveryRequest()

    def test_valid_criteria_accepted(self):
        criteria = CompanyDiscoveryRequest(industry="  fintech  ")
        assert criteria.industry == "fintech"

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
