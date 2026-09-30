import random

from felix.render.sound import SoundPlayer


class FakeEffect:
    played = []

    def __init__(self, path):
        self.path = path

    def play(self):
        FakeEffect.played.append(self.path.name)


def make_player(tmp_path, names):
    for n in names:
        (tmp_path / n).write_bytes(b"RIFF")
    FakeEffect.played = []
    return SoundPlayer(tmp_path, factory=FakeEffect, rng=random.Random(0))


def test_event_plays_one_of_its_variants(tmp_path):
    player = make_player(tmp_path, ["meow1.wav", "meow2.wav", "purr.wav"])
    for _ in range(10):
        player.play("meow")
    assert set(FakeEffect.played) == {"meow1.wav", "meow2.wav"}


def test_unknown_event_is_ignored(tmp_path):
    player = make_player(tmp_path, ["meow1.wav"])
    player.play("bark")
    assert FakeEffect.played == []


def test_muted_player_stays_silent(tmp_path):
    player = make_player(tmp_path, ["purr.wav"])
    player.enabled = False
    player.play("purr")
    assert FakeEffect.played == []
