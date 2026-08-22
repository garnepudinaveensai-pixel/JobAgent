from app.agents.agent_brain import LocalAgentBrain


def test_exceptionally_strong_recent_urgent_candidate_gets_very_high_priority():
    priority = LocalAgentBrain.rank_priority(
        target=True,
        freshness=100,
        urgency=100,
        match_score=95,
        eligibility=100,
    )

    assert priority >= 90
    assert priority <= 100


def test_recent_urgent_job_without_match_data_still_gets_meaningful_priority():
    priority = LocalAgentBrain.rank_priority(
        target=True,
        freshness=100,
        urgency=100,
        match_score=0,
        eligibility=55,
    )

    assert priority > 50
    assert priority < 90


def test_high_match_eligible_job_gets_high_priority():
    priority = LocalAgentBrain.rank_priority(
        target=True,
        freshness=65,
        urgency=0,
        match_score=95,
        eligibility=100,
    )

    assert priority >= 60


def test_low_match_job_has_lower_priority():
    priority = LocalAgentBrain.rank_priority(
        target=True,
        freshness=65,
        urgency=0,
        match_score=40,
        eligibility=100,
    )

    assert priority < 65


def test_ineligible_job_is_not_high_priority():
    priority = LocalAgentBrain.rank_priority(
        target=True,
        freshness=100,
        urgency=100,
        match_score=95,
        eligibility=0,
    )

    assert priority < 85


def test_non_target_always_has_zero_priority():
    priority = LocalAgentBrain.rank_priority(
        target=False,
        freshness=100,
        urgency=100,
        match_score=100,
        eligibility=100,
    )

    assert priority == 0


def test_priority_is_always_bounded():
    values = (
        (0, 0, 0, 0),
        (100, 100, 100, 100),
        (200, 200, 200, 200),
        (-50, -50, -50, -50),
    )

    for freshness, urgency, match, eligibility in values:
        priority = LocalAgentBrain.rank_priority(
            target=True,
            freshness=freshness,
            urgency=urgency,
            match_score=match,
            eligibility=eligibility,
        )

        assert 0 <= priority <= 100


def test_match_score_has_meaningful_effect():
    low_match = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=40,
        match_score=40,
        eligibility=100,
    )

    high_match = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=40,
        match_score=95,
        eligibility=100,
    )

    assert high_match > low_match


def test_eligibility_has_meaningful_effect():
    eligible = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=40,
        match_score=90,
        eligibility=100,
    )

    unknown = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=40,
        match_score=90,
        eligibility=55,
    )

    ineligible = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=40,
        match_score=90,
        eligibility=0,
    )

    assert eligible > unknown
    assert unknown > ineligible


def test_freshness_has_meaningful_effect():
    recent = LocalAgentBrain.rank_priority(
        target=True,
        freshness=100,
        urgency=20,
        match_score=90,
        eligibility=100,
    )

    old = LocalAgentBrain.rank_priority(
        target=True,
        freshness=20,
        urgency=20,
        match_score=90,
        eligibility=100,
    )

    assert recent > old


def test_urgency_has_meaningful_effect():
    urgent = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=100,
        match_score=90,
        eligibility=100,
    )

    normal = LocalAgentBrain.rank_priority(
        target=True,
        freshness=70,
        urgency=0,
        match_score=90,
        eligibility=100,
    )

    assert urgent > normal


def test_priority_inputs_are_numeric_and_stable():
    first = LocalAgentBrain.rank_priority(
        target=True,
        freshness=80,
        urgency=50,
        match_score=85,
        eligibility=100,
    )

    second = LocalAgentBrain.rank_priority(
        target=True,
        freshness=80,
        urgency=50,
        match_score=85,
        eligibility=100,
    )

    assert isinstance(first, float)
    assert first == second