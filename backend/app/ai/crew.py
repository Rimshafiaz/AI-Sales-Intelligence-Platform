from crewai import Crew, Process

from app.ai.tasks.news_task import create_news_task
from app.ai.tasks.pain_point_task import create_pain_point_task
from app.ai.tasks.research_task import create_research_task
from app.ai.tasks.reviewer_task import create_reviewer_task
from app.ai.tasks.strategy_task import create_strategy_task
from app.ai.tasks.technology_task import create_technology_task
from app.schemas.agent_outputs import (
    NewsAgentOutput,
    PainPointAgentOutput,
    ResearchAgentOutput,
    ReviewerOutput,
    StrategyAgentOutput,
    TechnologyAgentOutput,
)
from app.schemas.sales_intelligence_report import SalesIntelligenceReport


def _extract_pydantic(task, phase_label: str):
    output = task.output
    if output is None or output.pydantic is None:
        raise RuntimeError(
            f"{phase_label}: agent failed to produce valid structured output."
        )
    return output.pydantic


def _run_single_agent_crew(task, phase_label: str):
    crew = Crew(
        agents=[task.agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    crew.kickoff()
    return _extract_pydantic(task, phase_label)


def _run_phase_1(
    company_name: str,
    evidence_context: str,
) -> tuple[ResearchAgentOutput, TechnologyAgentOutput, NewsAgentOutput]:
    research_task = create_research_task(company_name, evidence_context)
    research = _run_single_agent_crew(research_task, "Phase 1 (Research)")

    technology_task = create_technology_task(company_name, evidence_context)
    technology = _run_single_agent_crew(technology_task, "Phase 1 (Technology)")

    news_task = create_news_task(company_name, evidence_context)
    news = _run_single_agent_crew(news_task, "Phase 1 (News)")

    return research, technology, news


def _run_phase_2(
    company_name: str,
    research: ResearchAgentOutput,
    technology: TechnologyAgentOutput,
    news: NewsAgentOutput,
) -> PainPointAgentOutput:
    pain_point_task = create_pain_point_task(
        company_name, research, technology, news,
    )
    return _run_single_agent_crew(pain_point_task, "Phase 2 (Pain Point)")


def _run_phase_3(
    company_name: str,
    research: ResearchAgentOutput,
    technology: TechnologyAgentOutput,
    news: NewsAgentOutput,
    pain_point: PainPointAgentOutput,
    guidance: str | None,
) -> StrategyAgentOutput:
    strategy_task = create_strategy_task(
        company_name, research, technology, news, pain_point,
        guidance=guidance,
    )
    return _run_single_agent_crew(strategy_task, "Phase 3 (Strategy)")


def _run_phase_4(
    company_name: str,
    evidence_context: str,
    research: ResearchAgentOutput,
    technology: TechnologyAgentOutput,
    news: NewsAgentOutput,
    pain_point: PainPointAgentOutput,
    strategy: StrategyAgentOutput,
) -> ReviewerOutput:
    reviewer_task = create_reviewer_task(
        company_name,
        evidence_context,
        research,
        technology,
        news,
        pain_point,
        strategy,
    )
    return _run_single_agent_crew(reviewer_task, "Phase 4 (Reviewer)")


def _assemble_report(
    research: ResearchAgentOutput,
    technology: TechnologyAgentOutput,
    news: NewsAgentOutput,
    pain_point: PainPointAgentOutput,
    strategy: StrategyAgentOutput,
) -> SalesIntelligenceReport:
    return SalesIntelligenceReport(
        executive_summary=strategy.executive_summary,
        company_profile=research.company_profile,
        technologies=technology.technologies,
        business_signals=news.business_signals,
        opportunity_assessment=strategy.opportunity_assessment,
        contact_recommendation=strategy.contact_recommendation,
        confidence=strategy.confidence,
        pain_points=pain_point.pain_points,
        strategy=strategy.strategy,
        suggested_decision_makers=strategy.suggested_decision_makers,
        personalized_outreach=strategy.personalized_outreach,
        caveats=strategy.caveats,
    )


def run_sales_intelligence_crew(
    company_name: str,
    evidence_context: str,
    guidance: str | None = None,
) -> SalesIntelligenceReport:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    clean_evidence = evidence_context.strip()
    if not clean_evidence:
        raise ValueError("Evidence context cannot be blank.")

    clean_guidance = guidance.strip() if guidance else None

    research, technology, news = _run_phase_1(
        clean_company_name, clean_evidence,
    )

    pain_point = _run_phase_2(
        clean_company_name, research, technology, news,
    )

    strategy = _run_phase_3(
        clean_company_name, research, technology, news, pain_point,
        clean_guidance,
    )

    reviewer = _run_phase_4(
        clean_company_name,
        clean_evidence,
        research,
        technology,
        news,
        pain_point,
        strategy,
    )

    if not reviewer.approved:
        raise ValueError(
            f"Reviewer rejected report: {'; '.join(reviewer.issues)}"
        )

    return _assemble_report(research, technology, news, pain_point, strategy)
