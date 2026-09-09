from crewai import Crew, Process

from app.ai.tasks.news_task import create_news_task
from app.ai.tasks.pain_point_task import create_pain_point_task
from app.ai.tasks.research_task import create_research_task
from app.ai.tasks.reviewer_task import create_reviewer_task
from app.ai.tasks.strategy_task import create_strategy_task
from app.ai.tasks.technology_task import create_technology_task
from app.ai.tasks.prospect_evidence_brief_tasks import (
    create_brief_business_context_task,
    create_brief_digital_presence_task,
    create_brief_evidence_quality_review_task,
    create_brief_opportunity_diagnosis_task,
    create_brief_public_traction_task,
    create_brief_strategy_outreach_task,
)
from app.schemas.agent_outputs import (
    BriefFindingsOutput,
    BriefStrategyOutput,
    NewsAgentOutput,
    PainPointAgentOutput,
    ResearchAgentOutput,
    ReviewerOutput,
    StrategyAgentOutput,
    TechnologyAgentOutput,
)
from app.schemas.opportunity_qualification import OpportunityQualificationState
from app.schemas.prospect_evidence_brief import (
    BriefEvidenceQuality,
    BriefFinding,
    BriefQualification,
    GroundedOutreachDraft,
    PitchAngle,
    ProspectEvidenceBrief,
    ProspectEvidenceBriefHandoffs,
)
from app.schemas.sales_intelligence_report import SalesIntelligenceReport
from app.services.prospect_evidence_brief_review import require_approved_prospect_evidence_brief


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
    objective_context: str | None,
) -> PainPointAgentOutput:
    pain_point_task = create_pain_point_task(
        company_name, research, technology, news,
        objective_context=objective_context,
    )
    return _run_single_agent_crew(pain_point_task, "Phase 2 (Pain Point)")


def _run_phase_3(
    company_name: str,
    research: ResearchAgentOutput,
    technology: TechnologyAgentOutput,
    news: NewsAgentOutput,
    pain_point: PainPointAgentOutput,
    guidance: str | None,
    objective_context: str | None,
) -> StrategyAgentOutput:
    strategy_task = create_strategy_task(
        company_name, research, technology, news, pain_point,
        guidance=guidance,
        objective_context=objective_context,
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
    objective_context: str | None = None,
) -> SalesIntelligenceReport:
    clean_company_name = company_name.strip()
    if not clean_company_name:
        raise ValueError("Company name cannot be blank.")

    clean_evidence = evidence_context.strip()
    if not clean_evidence:
        raise ValueError("Evidence context cannot be blank.")

    clean_guidance = guidance.strip() if guidance else None
    clean_objective_context = (
        objective_context.strip() if objective_context else None
    )

    research, technology, news = _run_phase_1(
        clean_company_name, clean_evidence,
    )

    pain_point = _run_phase_2(
        clean_company_name, research, technology, news,
        clean_objective_context,
    )

    strategy = _run_phase_3(
        clean_company_name, research, technology, news, pain_point,
        clean_guidance,
        clean_objective_context,
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


def run_prospect_evidence_brief_crew(
    handoffs: ProspectEvidenceBriefHandoffs,
) -> ProspectEvidenceBrief:
    business_context = _run_single_agent_crew(
        create_brief_business_context_task(handoffs.business_context),
        "Brief business context",
    )
    digital_presence = _run_single_agent_crew(
        create_brief_digital_presence_task(handoffs.digital_presence),
        "Brief digital presence",
    )
    public_traction = _run_single_agent_crew(
        create_brief_public_traction_task(handoffs.public_traction),
        "Brief public traction",
    )
    opportunity_diagnosis = _run_single_agent_crew(
        create_brief_opportunity_diagnosis_task(handoffs.opportunity_diagnosis),
        "Brief opportunity diagnosis",
    )
    finding_outputs = [
        business_context,
        digital_presence,
        public_traction,
        opportunity_diagnosis,
    ]
    strategy = _run_single_agent_crew(
        create_brief_strategy_outreach_task(
            handoffs.strategy_outreach,
            finding_outputs,
        ),
        "Brief strategy and outreach",
    )
    brief = assemble_prospect_evidence_brief(
        handoffs,
        finding_outputs,
        strategy,
    )
    reviewer = _run_single_agent_crew(
        create_brief_evidence_quality_review_task(
            handoffs.evidence_quality_review,
            brief,
        ),
        "Brief evidence quality review",
    )
    return require_approved_prospect_evidence_brief(handoffs, brief, reviewer)


def assemble_prospect_evidence_brief(
    handoffs: ProspectEvidenceBriefHandoffs,
    finding_outputs: list[BriefFindingsOutput],
    strategy: BriefStrategyOutput,
) -> ProspectEvidenceBrief:
    context = handoffs.evidence_quality_review.context
    verdict = _select_brief_verdict(context.qualifications)
    evidence_keys = {evidence.key for evidence in context.evidence}
    findings = _unique_findings(finding_outputs, evidence_keys)
    caveats = _unique_caveats(finding_outputs, strategy)
    is_likely = verdict.state is OpportunityQualificationState.LIKELY
    pitch_angle = (
        PitchAngle.model_validate(strategy.pitch_angle.model_dump())
        if is_likely
        and strategy.pitch_angle is not None
        and strategy.pitch_angle.offering == context.objective.offering
        and set(strategy.pitch_angle.evidence_keys) <= evidence_keys
        else None
    )
    outreach_drafts = (
        [
            GroundedOutreachDraft.model_validate(draft.model_dump())
            for draft in strategy.outreach_drafts
            if draft.offering == context.objective.offering
            and all(set(grounding.evidence_keys) <= evidence_keys for grounding in draft.grounding)
        ]
        if is_likely
        else []
    )
    return ProspectEvidenceBrief(
        objective=context.objective,
        prospect=context.prospect,
        verdict=verdict,
        evidence_quality=_brief_evidence_quality(verdict),
        findings=findings,
        contacts=context.contacts,
        pitch_angle=pitch_angle,
        outreach_drafts=outreach_drafts,
        caveats=caveats,
        evidence=context.evidence,
        sources=context.sources,
    )


def _select_brief_verdict(
    qualifications: list[BriefQualification],
) -> BriefQualification:
    priorities = {
        OpportunityQualificationState.LIKELY: 0,
        OpportunityQualificationState.INSUFFICIENT_EVIDENCE: 1,
        OpportunityQualificationState.NOT_ELIGIBLE: 2,
    }
    return min(
        qualifications,
        key=lambda item: (priorities[item.state], item.opportunity_model_id),
    )


def _brief_evidence_quality(verdict: BriefQualification) -> BriefEvidenceQuality:
    if verdict.state is OpportunityQualificationState.LIKELY:
        if len(verdict.supporting_evidence_keys) >= 2:
            return BriefEvidenceQuality.HIGH
        return BriefEvidenceQuality.MEDIUM
    return BriefEvidenceQuality.NEEDS_REVIEW


def _unique_findings(
    outputs: list[BriefFindingsOutput],
    evidence_keys: set[str],
) -> list[BriefFinding]:
    findings = []
    seen = set()
    for output in outputs:
        for finding in output.findings:
            if not set(finding.evidence_keys) <= evidence_keys:
                continue
            key = finding.statement.casefold()
            if key not in seen:
                findings.append(BriefFinding.model_validate(finding.model_dump()))
                seen.add(key)
    return findings[:12]


def _unique_caveats(
    outputs: list[BriefFindingsOutput],
    strategy: BriefStrategyOutput,
) -> list[str]:
    caveats = []
    seen = set()
    for caveat in [
        *(value for output in outputs for value in output.caveats),
        *strategy.caveats,
    ]:
        normalized = caveat.strip()
        if normalized and normalized.casefold() not in seen:
            caveats.append(normalized)
            seen.add(normalized.casefold())
    return caveats[:10]
