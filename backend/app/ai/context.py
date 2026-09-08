from app.models.research_source import ResearchSource
from app.schemas.evidence_gate import SourceAdmissionState


MAX_EVIDENCE_SOURCES = 12
MAX_EVIDENCE_EXCERPT_LENGTH = 600


def build_research_evidence_context(sources: list[ResearchSource]) -> str:
    if not sources:
        raise ValueError("Evidence context requires at least one research source.")
    if any(source.admission_state is not SourceAdmissionState.ACCEPTED for source in sources):
        raise ValueError("Evidence context may contain only accepted research sources.")

    source_blocks: list[str] = []

    for source in sources[:MAX_EVIDENCE_SOURCES]:
        lines = [
            f"URL: {source.url}",
            f"Type: {source.source_type}",
        ]

        if source.title:
            lines.append(f"Title: {source.title}")

        if source.excerpt:
            excerpt = " ".join(source.excerpt.split())
            lines.append(f"Excerpt: {excerpt[:MAX_EVIDENCE_EXCERPT_LENGTH]}")

        source_blocks.append("\n".join(lines))

    return "Evidence sources:\n\n" + "\n\n".join(source_blocks)
