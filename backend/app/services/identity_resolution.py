"""Deterministic business-identity resolution for collected sources.

Replaces exact-substring name matching with a multi-signal resolver:
fuzzy name similarity (rapidfuzz), domain-stem compatibility, geography
support, and exact contact matches. No LLM, no embeddings, no network.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlsplit

from rapidfuzz.fuzz import token_set_ratio


STRONG_NAME_SCORE = 80
REASONABLE_NAME_SCORE = 60
DIFFERENT_NAME_SCORE = 50

LEGAL_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "pvt", "private", "co", "company",
    "corp", "corporation", "gmbh", "pc",
}

# Business-type words that materially change the entity when they appear
# in a source name but not in the candidate name (brand-root protection).
ENTITY_TYPE_WORDS = {
    "store", "hospital", "lab", "hotel", "pharmacy", "salon", "clinic",
    "shop", "mart", "restaurant", "cafe", "bakery", "gym", "school",
    "institute", "center", "centre",
}

# Generic tokens in domain stems that carry no identity meaning.
DOMAIN_NOISE_TOKENS = {"www", "official", "online", "site", "web", "com"}

# Cities used only to detect explicit geographic conflicts between the
# resolved business location and a source that names a different city.
KNOWN_CITIES = {
    "lahore", "karachi", "islamabad", "rawalpindi", "multan", "faisalabad",
    "peshawar", "quetta", "sialkot", "gujranwala", "toronto", "vancouver",
    "montreal", "london", "sydney", "melbourne", "dubai", "delhi", "mumbai",
}

NON_NAME_TOKENS = {"and", "the", "of", "for"}


def normalize_company_name(value: str) -> str:
    text = value.casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[-_/]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\bcentre\b", "center", text)
    tokens = [
        token
        for token in text.split()
        if token and token not in LEGAL_SUFFIXES
    ]
    return " ".join(tokens)


def significant_tokens(value: str) -> list[str]:
    return [
        token
        for token in normalize_company_name(value).split()
        if token not in NON_NAME_TOKENS
    ]


def identity_name_score(
    candidate_name: str,
    source_name: str,
) -> int:
    candidate = normalize_company_name(candidate_name)
    source = normalize_company_name(source_name)
    if not candidate or not source:
        return 0
    return int(token_set_ratio(candidate, source))


def extra_entity_type_word(
    candidate_tokens: list[str],
    source_tokens: list[str],
) -> str | None:
    for token in source_tokens:
        if token in ENTITY_TYPE_WORDS and token not in candidate_tokens:
            return token
    return None


def domain_stem(url: str) -> str:
    hostname = urlsplit(url).hostname
    if not hostname:
        return ""
    label = hostname.casefold().removesuffix(".com").removesuffix(".pk")
    return label.removeprefix("www.")


def domain_matches_name(
    stem: str,
    candidate_tokens: list[str],
) -> bool:
    if not stem:
        return False
    compact = "".join(candidate_tokens)
    if compact and (compact in stem or stem in compact):
        return True
    matched = 0
    for token in candidate_tokens:
        if len(token) >= 2 and token in stem:
            matched += 1
    return matched >= 2


def domain_conflicts_with_name(
    stem: str,
    candidate_tokens: list[str],
) -> str | None:
    residual = stem
    for token in sorted(set(candidate_tokens), key=len, reverse=True):
        if token:
            residual = residual.replace(token, " ")
    residual = re.sub(r"[^a-z]", "", residual)
    if residual in DOMAIN_NOISE_TOKENS or not residual:
        return None
    return residual if residual in ENTITY_TYPE_WORDS else None


def location_supports(
    candidate_location: str | None,
    source_text: str,
) -> bool | None:
    if not candidate_location:
        return None
    normalized = candidate_location.casefold().strip()
    if not normalized:
        return None
    lowered = source_text.casefold()
    if normalized in lowered:
        return True
    for city in KNOWN_CITIES:
        if city != normalized and re.search(rf"\b{re.escape(city)}\b", lowered):
            return False
    return None


def contact_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def contact_matches(
    candidate_phone: str | None,
    source_text: str,
) -> bool | None:
    if not candidate_phone:
        return None
    digits = contact_digits(candidate_phone)
    if len(digits) < 7:
        return None
    tail = digits[-9:]
    return tail in contact_digits(source_text)


class IdentityStatus(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IdentityResolution:
    status: IdentityStatus
    name_score: int
    domain_match: bool
    location_match: bool | None
    contact_match: bool | None
    extra_entity_word: str | None = None
    reasons: list[str] = field(default_factory=list)


def resolve_source_identity(
    candidate_name: str,
    candidate_location: str | None,
    candidate_phone: str | None,
    source_url: str,
    source_name: str,
    source_text: str,
    identity_verified: bool = False,
) -> IdentityResolution:
    candidate_tokens = significant_tokens(candidate_name)
    title_score = identity_name_score(candidate_name, source_name)
    excerpt_score = (
        identity_name_score(candidate_name, source_text)
        if source_text.strip()
        else 0
    )
    name_score = max(title_score, excerpt_score)
    stem = domain_stem(source_url)
    domain_match = domain_matches_name(stem, candidate_tokens)
    extra_word = extra_entity_type_word(
        candidate_tokens, normalize_company_name(source_name).split()
    )
    domain_conflict = domain_conflicts_with_name(stem, candidate_tokens)
    source_body = f"{source_name} {source_text}".casefold()
    location_match = location_supports(candidate_location, source_body)
    contact_match = contact_matches(candidate_phone, source_body)

    reasons: list[str] = []

    if name_score < DIFFERENT_NAME_SCORE:
        return IdentityResolution(
            status=IdentityStatus.REJECTED,
            name_score=name_score,
            domain_match=domain_match,
            location_match=location_match,
            contact_match=contact_match,
            extra_entity_word=extra_word,
            reasons=[
                "The source name does not resemble the resolved business name.",
            ],
        )

    strong_name = name_score >= STRONG_NAME_SCORE
    reasonable_name = name_score >= REASONABLE_NAME_SCORE
    no_contradiction = location_match is not False and domain_conflict is None

    shared_tokens = len(
        set(candidate_tokens) & set(normalize_company_name(source_name).split())
    )

    if shared_tokens < 2 and not domain_match and not contact_match:
        if (
            identity_verified
            and name_score >= 70
            and location_match
        ):
            reasons.append(
                "The provider record verified this business identity and the "
                "source names it at the resolved location."
            )
            return IdentityResolution(
                status=IdentityStatus.CONFIRMED,
                name_score=name_score,
                domain_match=domain_match,
                location_match=location_match,
                contact_match=contact_match,
                extra_entity_word=extra_word,
                reasons=reasons,
            )
        reasons.append(
            "The source shares too few distinctive name tokens with the "
            "resolved business."
        )
        return IdentityResolution(
            status=IdentityStatus.REJECTED,
            name_score=name_score,
            domain_match=domain_match,
            location_match=location_match,
            contact_match=contact_match,
            extra_entity_word=extra_word,
            reasons=reasons,
        )
        reasons.append(
            "The source shares too few distinctive name tokens with the "
            "resolved business."
        )
        return IdentityResolution(
            status=IdentityStatus.REJECTED,
            name_score=name_score,
            domain_match=domain_match,
            location_match=location_match,
            contact_match=contact_match,
            extra_entity_word=extra_word,
            reasons=reasons,
        )

    if (
        reasonable_name
        and not extra_word
        and no_contradiction
        and (domain_match and location_match)
    ):
        reasons.append(
            "The source name matches the business, its domain represents the "
            "business name, and the location is supported."
        )
        return IdentityResolution(
            status=IdentityStatus.CONFIRMED,
            name_score=name_score,
            domain_match=domain_match,
            location_match=location_match,
            contact_match=contact_match,
            extra_entity_word=extra_word,
            reasons=reasons,
        )
    if contact_match and reasonable_name and no_contradiction:
        reasons.append(
            "The source reproduces the business's own contact information."
        )
        return IdentityResolution(
            status=IdentityStatus.CONFIRMED,
            name_score=name_score,
            domain_match=domain_match,
            location_match=location_match,
            contact_match=contact_match,
            extra_entity_word=extra_word,
            reasons=reasons,
        )

    if extra_word:
        reasons.append(
            f"The source name carries the extra business-type word "
            f"'{extra_word}', so it may describe a different business."
        )
    if not no_contradiction:
        if domain_conflict is not None:
            reasons.append(
                f"The domain suggests a different business type "
                f"('{domain_conflict}')."
            )
        if location_match is False:
            reasons.append("The source does not support the resolved location.")

    if strong_name and no_contradiction:
        status = IdentityStatus.PROBABLE
        if not reasons:
            reasons.append(
                "The source name strongly matches the business, but no domain "
                "or contact evidence corroborates it."
            )
    elif reasonable_name:
        status = IdentityStatus.PROBABLE if (
            domain_match and location_match
        ) else IdentityStatus.AMBIGUOUS
        if status is IdentityStatus.PROBABLE:
            reasons.append(
                "The source name reasonably matches the business and its "
                "domain and location corroborate it."
            )
        else:
            reasons.append(
                "The source name matches the business, but identity evidence "
                "is insufficient."
            )
    else:
        status = IdentityStatus.AMBIGUOUS
        reasons.append(
            "The source name only weakly matches the business name."
        )

    return IdentityResolution(
        status=status,
        name_score=name_score,
        domain_match=domain_match,
        location_match=location_match,
        contact_match=contact_match,
        extra_entity_word=extra_word,
        reasons=reasons,
    )
