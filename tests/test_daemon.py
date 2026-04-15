import pytest
from unittest.mock import AsyncMock, patch
from src.scrapers.daemon import _parse_targets, _run_concurrent_sweep


# ── _parse_targets ────────────────────────────────────────────────────────────

def test_parse_targets_cartesian_product():
    """2 roles × 2 locations → 4 pairs in row-major order (pipe-separated)."""
    result = _parse_targets(
        "Software Engineer Intern|Frontend Developer Intern",
        "Vancouver, BC|Remote Canada",
    )
    assert result == [
        ("Software Engineer Intern", "Vancouver, BC"),
        ("Software Engineer Intern", "Remote Canada"),
        ("Frontend Developer Intern", "Vancouver, BC"),
        ("Frontend Developer Intern", "Remote Canada"),
    ]


def test_parse_targets_strips_whitespace():
    """Leading/trailing whitespace around pipes must be stripped."""
    result = _parse_targets(
        "  Software Engineer Intern | Backend Developer Intern  ",
        "  Vancouver, BC  |  Remote Canada  ",
    )
    assert result == [
        ("Software Engineer Intern", "Vancouver, BC"),
        ("Software Engineer Intern", "Remote Canada"),
        ("Backend Developer Intern", "Vancouver, BC"),
        ("Backend Developer Intern", "Remote Canada"),
    ]


def test_parse_targets_single_role_single_location():
    """Single role + single location → 1 pair (backward compat)."""
    result = _parse_targets("Software Engineer", "Vancouver, BC")
    assert result == [("Software Engineer", "Vancouver, BC")]


def test_parse_targets_empty_strings_return_empty():
    """If either string is blank, return an empty list."""
    assert _parse_targets("", "Vancouver, BC") == []
    assert _parse_targets("Software Engineer Intern", "") == []
    assert _parse_targets("", "") == []


# ── _run_concurrent_sweep ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_concurrent_sweep_sums_saved_counts():
    """Each (user_id, role, loc) sweep runs and total saved count is summed."""
    mock_engine = AsyncMock()
    # Each run_sweep returns (saved_count, found_ids)
    mock_engine.run_sweep.side_effect = [
        (3, ["a", "b", "c"]),
        (2, ["d", "e"]),
        (0, []),
    ]
    targets = [
        (1, "Software Engineer Intern", "Vancouver BC"),
        (2, "Frontend Developer Intern", "Remote Canada"),
        (3, "Backend Developer Intern", "Toronto ON"),
    ]

    total = await _run_concurrent_sweep(mock_engine, targets, results_wanted=25)

    assert total == 5
    assert mock_engine.run_sweep.call_count == 3


@pytest.mark.asyncio
async def test_run_concurrent_sweep_passes_correct_args():
    """Each sweep must be called with the correct role, location, results_wanted."""
    mock_engine = AsyncMock()
    mock_engine.run_sweep.return_value = (1, ["x"])

    targets = [(1, "SWE Intern", "Vancouver BC"), (2, "Frontend Intern", "Remote")]
    await _run_concurrent_sweep(mock_engine, targets, results_wanted=30)

    calls = mock_engine.run_sweep.call_args_list
    assert calls[0].kwargs == {"role": "SWE Intern", "location": "Vancouver BC", "results_wanted": 30, "user_id": 1}
    assert calls[1].kwargs == {"role": "Frontend Intern", "location": "Remote", "results_wanted": 30, "user_id": 2}


@pytest.mark.asyncio
async def test_run_concurrent_sweep_one_failure_does_not_crash_others():
    """If one sweep raises an exception, remaining sweeps must still complete."""
    mock_engine = AsyncMock()
    mock_engine.run_sweep.side_effect = [
        Exception("LinkedIn rate-limited"),  # sweep 1 fails
        (4, ["a", "b", "c", "d"]),           # sweep 2 succeeds
    ]
    targets = [
        (1, "SWE Intern", "Vancouver BC"),
        (2, "Frontend Intern", "Remote"),
    ]

    total = await _run_concurrent_sweep(mock_engine, targets, results_wanted=25)

    # Failed sweep contributes 0; successful sweep contributes 4
    assert total == 4


@pytest.mark.asyncio
async def test_run_concurrent_sweep_empty_targets_returns_zero():
    """No targets → no sweeps run, total is 0."""
    mock_engine = AsyncMock()
    total = await _run_concurrent_sweep(mock_engine, [], results_wanted=25)
    assert total == 0
    mock_engine.run_sweep.assert_not_called()
