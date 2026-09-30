from felix.paths import find_sprites_dir, user_data_dir


def make_sprites(d):
    d.mkdir(parents=True)
    (d / "fig_100.png").write_bytes(b"png")
    return d


def test_env_override_wins(tmp_path):
    custom = make_sprites(tmp_path / "custom")
    env = {"FELIX_ASSETS": str(custom)}
    assert find_sprites_dir(env=env, candidates=[make_sprites(tmp_path / "other")]) == custom


def test_first_candidate_with_sprites(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    good = make_sprites(tmp_path / "good")
    assert find_sprites_dir(env={}, candidates=[empty, tmp_path / "missing", good]) == good


def test_none_when_no_sprites(tmp_path):
    assert find_sprites_dir(env={}, candidates=[tmp_path]) is None


def test_user_data_dir_per_platform(tmp_path):
    assert user_data_dir({"LOCALAPPDATA": str(tmp_path)}, "win32") == tmp_path / "felix"
    assert user_data_dir({"XDG_DATA_HOME": str(tmp_path)}, "linux") == tmp_path / "felix"
    assert user_data_dir({"HOME": str(tmp_path)}, "linux") == tmp_path / ".local" / "share" / "felix"
