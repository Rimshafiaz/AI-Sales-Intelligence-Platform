from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.opportunity_models import (
    CandidateIdentity,
    EvidenceSignal,
    EvidenceSignalType,
    EvidenceSource,
    EvidenceType,
    IdentityState,
    OpportunityModelSelection,
)
from app.services.opportunity_model_catalog import (
    INDUSTRY_OVERLAYS,
    OPPORTUNITY_MODELS,
    get_opportunity_model,
    list_opportunity_models,
)


NOW = datetime(2026, 9, 7, tzinfo=UTC)


def source() -> EvidenceSource:
    return EvidenceSource(
        provider="google_places",
        provider_record_id="ChIJ-example",
        retrieved_at=NOW,
    )


class TestOpportunityModelCatalog:
    def test_initial_catalog_has_web_and_social_models(self):
        assert len(OPPORTUNITY_MODELS) == 9
        assert get_opportunity_model(
            "web_conversion.booking_contact_path"
        ).display_name == "Appointment or inquiry path"
        assert len(list_opportunity_models()) == 9

    def test_industry_coverage_is_explicit(self):
        social = get_opportunity_model("social_presence.dormant_official_presence")
        assert len(social.applicable_industries) == 4
        assert INDUSTRY_OVERLAYS.keys() - set(social.applicable_industries)

    def test_booking_and_restaurant_models_require_distinct_evidence(self):
        booking = get_opportunity_model("web_conversion.booking_contact_path")
        restaurant = get_opportunity_model(
            "web_conversion.restaurant_reservation_path"
        )

        assert EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY in booking.required_signal_types
        assert EvidenceSignalType.WEBSITE_RESERVATION_PATH_MANUAL_ONLY in restaurant.required_signal_types


class TestEvidenceContracts:
    def test_evidence_requires_a_record_id_or_url(self):
        with pytest.raises(ValidationError, match="provider record ID or a source URL"):
            EvidenceSource(provider="google_places", retrieved_at=NOW)

    def test_inference_requires_explicit_basis(self):
        with pytest.raises(ValidationError, match="inference must include"):
            EvidenceSignal(
                signal_type=EvidenceSignalType.WEBSITE_BOOKING_PATH_MANUAL_ONLY,
                evidence_type=EvidenceType.INFERENCE,
                supporting_value="Booking link directs to WhatsApp.",
                source=source(),
                captured_at=NOW,
            )

    def test_measurements_can_keep_a_numeric_value_for_later_qualification(self):
        signal = EvidenceSignal(
            signal_type=EvidenceSignalType.WEBSITE_MOBILE_PERFORMANCE_MEASURED,
            evidence_type=EvidenceType.OBSERVED,
            supporting_value="PageSpeed mobile performance score.",
            numeric_value=31,
            source=source(),
            captured_at=NOW,
        )
        assert signal.numeric_value == 31


class TestIdentityAndSelectionContracts:
    def test_only_catalog_model_ids_can_be_selected(self):
        with pytest.raises(ValidationError):
            OpportunityModelSelection(model_ids=("ai_automation.workflow",))

    def test_model_selection_rejects_duplicates(self):
        with pytest.raises(ValidationError, match="only once"):
            OpportunityModelSelection(
                model_ids=(
                    "web_conversion.mobile_performance",
                    "web_conversion.mobile_performance",
                )
            )

    def test_identity_keeps_its_verification_state_and_source(self):
        identity = CandidateIdentity(
            canonical_name="Glow Studio",
            business_category="Beauty salon",
            location="Lahore",
            identity_state=IdentityState.VERIFIED,
            primary_source=source(),
        )
        assert identity.identity_state is IdentityState.VERIFIED
