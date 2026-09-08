from app.integrations.search_provider import CollectedSource
from app.models.company import Company
from app.models.research_request import ResearchRequest
from app.schemas.evidence_gate import EvidenceGateState, SourceAdmissionState
from app.services.evidence_gate import EvidenceGateTarget, review_sources, target_from_research_request


def target() -> EvidenceGateTarget:
    return EvidenceGateTarget(
        company_name="Aleezay Hair Beauty Care Salon",
        location="Lahore",
        official_origin="https://aleezay.example",
        official_website="https://aleezay.example/",
        identity_verified=True,
        trusted_source_urls=frozenset({"https://aleezay.example/"}),
    )


class TestEvidenceGate:
    def test_uses_the_verified_manual_target_snapshot(self):
        company = Company(name="Glow Salon")
        request = ResearchRequest(
            objective={
                "location": "Lahore",
                "resolved_target": {
                    "business_name": "Glow Salon",
                    "website": "https://glowsalon.example",
                    "identity_state": "verified",
                    "source": {"source_url": "https://glowsalon.example/about"},
                },
            }
        )

        resolved_target = target_from_research_request(request, company)

        assert resolved_target.identity_verified is True
        assert resolved_target.official_origin == "https://glowsalon.example"
        assert resolved_target.location == "Lahore"

    def test_accepts_a_source_on_the_verified_official_domain(self):
        admissions, result = review_sources(
            target(),
            [
                CollectedSource(
                    url="https://aleezay.example/services",
                    title="Services",
                    excerpt="Hair and beauty services in Lahore.",
                    source_type="company_website",
                )
            ],
        )

        assert result.state is EvidenceGateState.READY_FOR_DEEPER_RESEARCH
        assert admissions[0].state is SourceAdmissionState.ACCEPTED

    def test_aleezay_style_mixed_sources_need_review_without_accepted_evidence(self):
        admissions, result = review_sources(
            target(),
            [
                CollectedSource(
                    url="https://directory.example/aleezay",
                    title="Aleezay Hair Beauty Care Salon in Islamabad",
                    excerpt="A beauty directory listing.",
                ),
                CollectedSource(
                    url="https://instagram.com/hayazbeautysalon",
                    title="Hayaz Salon | Lahore",
                    excerpt="Appointments and services.",
                ),
                CollectedSource(
                    url="https://companies.example/alizay-beauty",
                    title="Alizay Beauty Ltd",
                    excerpt="Company overview in the United Kingdom.",
                ),
            ],
        )

        assert result.state is EvidenceGateState.NEEDS_REVIEW
        assert [admission.state for admission in admissions] == [
            SourceAdmissionState.NEEDS_REVIEW,
            SourceAdmissionState.EXCLUDED,
            SourceAdmissionState.EXCLUDED,
        ]

    def test_does_not_accept_a_name_only_result_without_location_support(self):
        admissions, result = review_sources(
            target(),
            [
                CollectedSource(
                    url="https://directory.example/aleezay",
                    title="Aleezay Hair Beauty Care Salon",
                    excerpt="Business profile.",
                )
            ],
        )

        assert result.state is EvidenceGateState.NEEDS_REVIEW
        assert admissions[0].state is SourceAdmissionState.NEEDS_REVIEW

    def test_requires_verified_target_identity_even_with_a_trusted_source(self):
        unverified_target = EvidenceGateTarget(
            company_name="Glow Salon",
            location="Lahore",
            official_origin=None,
            official_website=None,
            identity_verified=False,
            trusted_source_urls=frozenset({"https://directory.example/glow"}),
        )

        admissions, result = review_sources(
            unverified_target,
            [CollectedSource(url="https://directory.example/glow", title="Glow Salon", excerpt=None)],
        )

        assert admissions[0].state is SourceAdmissionState.ACCEPTED
        assert result.state is EvidenceGateState.NEEDS_REVIEW
