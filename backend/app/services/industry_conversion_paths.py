from dataclasses import dataclass
from urllib.parse import urlparse

from app.schemas.opportunity_models import EvidenceSignalType, IndustryOverlayId


@dataclass(frozen=True)
class ConversionPathFinding:
    signal_type: EvidenceSignalType
    supporting_value: str


PATH_TERMS = {
    "appointment": ("appointment", "book now", "schedule"),
    "classes": ("class", "timetable", "schedule"),
    "contact": ("contact", "mailto:", "tel:", "wa.me", "whatsapp"),
    "location": ("location", "directions", "find us", "maps"),
    "membership": ("membership", "join", "enrol", "enroll"),
    "menu": ("menu",),
    "ordering": ("order online", "delivery", "takeaway", "pickup"),
    "products": ("shop", "store", "product", "collection", "catalog", "catalogue"),
    "reservation": ("reservation", "reserve", "book a table"),
    "services": ("service", "treatment", "procedure"),
    "social": ("instagram.com", "facebook.com", "tiktok.com"),
    "trainers": ("trainer", "coach"),
    "trial": ("trial", "free pass", "guest pass"),
}


def analyze_conversion_paths(
    industry: IndustryOverlayId,
    links: tuple[tuple[str, str], ...],
) -> ConversionPathFinding | None:
    observed = _observed_paths(links)
    if industry is IndustryOverlayId.RESTAURANTS_CAFES:
        missing = []
        if not observed.intersection({"menu", "ordering"}):
            missing.append("a menu or online-order path")
        if not observed.intersection({"reservation", "location", "contact"}):
            missing.append("a reservation, location, or contact path")
        return _finding(
            EvidenceSignalType.WEBSITE_RESTAURANT_PRIMARY_PATH_NOT_OBSERVED,
            "restaurant",
            missing,
        )
    if industry is IndustryOverlayId.FITNESS_GYMS:
        missing = [] if observed.intersection(
            {"trial", "membership", "classes", "trainers", "contact"}
        ) else ["a trial, membership, class, trainer, or contact path"]
        return _finding(
            EvidenceSignalType.WEBSITE_FITNESS_ENQUIRY_PATH_NOT_OBSERVED,
            "fitness",
            missing,
        )
    if industry is IndustryOverlayId.BOUTIQUES_RETAIL:
        missing = [] if observed.intersection(
            {"products", "contact", "social"}
        ) else ["a catalogue, store, product-enquiry, contact, or social path"]
        return _finding(
            EvidenceSignalType.WEBSITE_RETAIL_PRODUCT_PATH_NOT_OBSERVED,
            "retail",
            missing,
        )
    if industry is IndustryOverlayId.DENTAL_SELECTED_CLINICS:
        missing = []
        if "services" not in observed:
            missing.append("treatment or service navigation")
        if not observed.intersection({"appointment", "contact"}):
            missing.append("an appointment or contact path")
        if not observed.intersection({"location", "contact"}):
            missing.append("a location or contact path")
        return _finding(
            EvidenceSignalType.WEBSITE_CLINIC_PATIENT_PATH_INCOMPLETE,
            "clinic",
            missing,
        )
    return None


def _observed_paths(links: tuple[tuple[str, str], ...]) -> set[str]:
    searchable = " ".join(
        f"{urlparse(url).path} {urlparse(url).netloc} {label}".casefold()
        for url, label in links
    )
    return {
        path
        for path, terms in PATH_TERMS.items()
        if any(term in searchable for term in terms)
    }


def _finding(
    signal_type: EvidenceSignalType,
    industry_label: str,
    missing: list[str],
) -> ConversionPathFinding | None:
    if not missing:
        return None
    return ConversionPathFinding(
        signal_type=signal_type,
        supporting_value=(
            f"The retrieved official {industry_label} homepage did not expose "
            + " or ".join(missing)
            + "."
        ),
    )
