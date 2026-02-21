from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_check_variant_weights_match_audience_rejects_mismatch():
    """Если сумма весов вариантов не равна audience_fraction (2+ варианта), возвращается ошибка."""
    from functions.experiments import _check_variant_weights_match_audience

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value={
            "audience_fraction": 0.5,
            "total_weight": 0.4,
            "variant_count": 2,
        }
    )
    err = await _check_variant_weights_match_audience(db, "any-id")
    assert err is not None
    assert "Сумма долей вариантов" in err
    assert "0.4" in err
    assert "0.5" in err
    assert "Отправка на одобрение невозможна" in err


@pytest.mark.asyncio
async def test_check_variant_weights_match_audience_accepts_match():
    """Если сумма весов равна audience_fraction (2+ варианта), ошибки нет."""
    from functions.experiments import _check_variant_weights_match_audience

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value={
            "audience_fraction": 0.5,
            "total_weight": 0.5,
            "variant_count": 2,
        }
    )
    err = await _check_variant_weights_match_audience(db, "any-id")
    assert err is None


@pytest.mark.asyncio
async def test_check_variant_weights_match_audience_skips_single_variant():
    """При одном варианте проверка суммы не выполняется (ошибки нет)."""
    from functions.experiments import _check_variant_weights_match_audience

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value={
            "audience_fraction": 0.5,
            "total_weight": 0.3,
            "variant_count": 1,
        }
    )
    err = await _check_variant_weights_match_audience(db, "any-id")
    assert err is None
