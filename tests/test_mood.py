import random

from felix.core.mood import ACTIVE, CALM, Temperament

BASE = {"walk": 10, "jump": 10, "stretch": 10, "sit": 10, "doze": 10, "wash": 10}


def test_the_cat_rarely_does_the_same_thing_twice_in_a_row():
    t = Temperament(random.Random(3), energy=0.5)
    picks = [t.pick(BASE) for _ in range(400)]
    repeats = sum(a == b for a, b in zip(picks, picks[1:]))
    assert repeats / len(picks) < 0.08  # sans mémoire : ~1/6 attendu
    assert not any(a == b == c for a, b, c in zip(picks, picks[1:], picks[2:]))


def share(t, names, n=600):
    level, picks = t.energy, []
    for _ in range(n):
        t.energy = level  # préférence mesurée à énergie constante (se reposer en redonne)
        picks.append(t.pick(BASE))
    return sum(p in names for p in picks) / n


def test_a_tired_cat_prefers_calm_activities_and_a_lively_one_active_ones():
    tired = Temperament(random.Random(1), energy=0.1, drift=False)
    lively = Temperament(random.Random(1), energy=0.9, drift=False)
    assert share(tired, CALM) > 0.6
    assert share(lively, ACTIVE) > 0.6


def test_energy_is_spent_by_activity_and_recovered_by_rest():
    t = Temperament(random.Random(2), energy=0.5)
    before = t.energy
    t.did("walk")
    assert t.energy < before
    t.did("doze")
    t.did("doze")
    assert t.energy > before - 0.05


def test_energy_drifts_slowly_but_stays_in_bounds():
    t = Temperament(random.Random(4), energy=0.5)
    values = []
    for _ in range(3600):
        t.tick(1.0)
        values.append(t.energy)
    assert 0.0 <= min(values) and max(values) <= 1.0
    assert max(values) - min(values) > 0.05  # elle bouge
    assert abs(values[1] - values[0]) < 0.01  # mais lentement
