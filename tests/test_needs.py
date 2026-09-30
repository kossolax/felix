import pytest

from felix.core.needs import Needs


def test_hunger_and_thirst_grow_with_time_and_saturate():
    n = Needs(hunger=0.0, thirst=0.0)
    n.tick(3600)
    assert n.hunger == pytest.approx(Needs.HUNGER_PER_HOUR)
    assert n.thirst == pytest.approx(Needs.THIRST_PER_HOUR)
    n.tick(100 * 3600)
    assert (n.hunger, n.thirst) == (1.0, 1.0)


def test_feeding_and_drinking_reset_the_gauges():
    n = Needs(hunger=0.9, thirst=0.8)
    n.feed()
    n.drink()
    assert (n.hunger, n.thirst) == (0.0, 0.0)


def test_saved_state_catches_up_on_elapsed_real_time():
    saved = Needs(hunger=0.1, thirst=0.1).to_dict(now=1000.0)
    n = Needs.from_dict(saved, now=1000.0 + 2 * 3600)
    assert n.hunger == pytest.approx(0.1 + 2 * Needs.HUNGER_PER_HOUR)


def test_catch_up_is_capped_and_garbage_gives_defaults():
    saved = Needs(hunger=0.0, thirst=0.0).to_dict(now=0.0)
    n = Needs.from_dict(saved, now=365 * 24 * 3600.0)
    assert n.hunger <= 1.0
    assert Needs.from_dict({"hunger": "??"}, now=0.0) == Needs()


def test_moods():
    assert Needs(hunger=0.8).hungry and not Needs(hunger=0.3).hungry
    assert Needs(thirst=0.9).thirsty
