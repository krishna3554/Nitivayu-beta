"""Structural checks for the deterministic demo dataset (no database required)."""

from scripts.seed_data import CHALLENGES, INDUSTRIES, MILESTONE_PLAN, OFFICERS, STAGE_STATUS, UNIVERSITIES


def test_challenge_universities_exist():
    codes = {u["short_code"] for u in UNIVERSITIES}
    for challenge in CHALLENGES:
        assert challenge["university"] in codes, f"{challenge['title']} references unknown university"


def test_challenge_stages_are_valid():
    for challenge in CHALLENGES:
        assert challenge["stage"] in STAGE_STATUS


def test_every_pipeline_stage_is_covered():
    stages = {c["stage"] for c in CHALLENGES}
    assert stages == {"pending", "offered", "accepted"}


def test_pledges_reference_known_industries():
    emails = {i["contact_email"] for i in INDUSTRIES}
    for challenge in CHALLENGES:
        for email, amount in challenge.get("pledges", []):
            assert email in emails
            assert amount > 0


def test_accepted_challenges_have_teams():
    for challenge in CHALLENGES:
        if challenge["stage"] == "accepted":
            assert challenge.get("team"), f"{challenge['title']} needs team info"


def test_milestones_numbered_within_contract():
    assert [m[0] for m in MILESTONE_PLAN] == [1, 2, 3]


def test_officer_emails_unique():
    emails = [o["email"] for o in OFFICERS]
    assert len(emails) == len(set(emails))
