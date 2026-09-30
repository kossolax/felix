from felix.__main__ import parse_args


def test_size_and_speed_are_command_line_options_for_tests():
    args = parse_args([])
    assert (args.scale, args.speed) == (1, 1.0)
    args = parse_args(["--scale", "2", "--speed", "3"])
    assert (args.scale, args.speed) == (2, 3.0)
