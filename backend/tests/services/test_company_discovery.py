from unittest.mock import patch

import pytest

from app.schemas.company_discovery import DiscoveryObjective, ParseDiscoveryRequest
from app.services.company_discovery import (
    check_supported_objective,
    parse_discovery_objective,
)


def objective(*, sectors: list[str] | None = None) -> DiscoveryObjective:
    return DiscoveryObjective(
        goal_type="client_prospecting",
        seller_role="Freelance web developer",
        offering="Website redesign",
        target_sectors=sectors or ["local businesses"],
        target_geographies=["Lahore"],
        search_queries=["local businesses Lahore", "businesses Lahore"],
        fit_rubric="Independent local businesses",
        desired_outcome="Find prospects",
    )


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ("Find dental practices in Lahore", "Dental & selected clinics"),
        ("Find dentists in Lahore", "Dental & selected clinics"),
        ("Find beauty salons in Lahore", "Beauty & wellness"),
    ],
)
def test_parser_normalizes_one_unambiguous_supported_vertical(
    goal: str, expected: str
):
    with patch(
        "app.services.company_discovery.run_goal_parser_task",
        return_value=objective(),
    ):
        parsed = parse_discovery_objective(ParseDiscoveryRequest(goal=goal))

    assert parsed.target_sectors == [expected]
    assert check_supported_objective(parsed, goal) == (True, None)
    assert check_supported_objective(parsed) == (True, None)


def test_generic_clinic_is_rejected_before_discovery():
    supported, message = check_supported_objective(
        objective(sectors=["clinics"]), "Find clinics in Lahore"
    )

    assert supported is False
    assert message and "Generic clinics are not supported yet" in message


def test_mixed_goal_requires_one_primary_vertical_before_discovery():
    goal = "Find clinics, dental practices, or wellness businesses in Lahore"
    supported, message = check_supported_objective(
        objective(sectors=["clinics", "dental practices", "wellness businesses"]),
        goal,
    )

    assert supported is False
    assert message and "more than one business category" in message
    assert "Dental & selected clinics" in message
    assert "Beauty & wellness" in message
    assert "Generic clinics are not supported yet" in message
