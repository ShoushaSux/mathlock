import random

import pytest

from mathlock.config import load_config
from mathlock.problems import Problem, generate


@pytest.mark.parametrize("difficulty", [1, 2, 3])
def test_answers_are_correct_nonnegative_ints(difficulty):
    rng = random.Random(1234)
    for _ in range(500):
        p = generate(difficulty, rng)
        expr = p.prompt.replace("×", "*").replace("÷", "//")
        assert eval(expr) == p.answer  # noqa: S307 - our own generated string
        assert p.answer >= 0
        if "÷" in p.prompt:
            a, b = (int(x) for x in p.prompt.split(" ÷ "))
            assert a % b == 0


def test_check_parses_input():
    p = Problem("2 + 2", 4)
    assert p.check(" 4 ")
    assert not p.check("5")
    assert not p.check("four")
    assert not p.check("")


def test_config_loading(tmp_path):
    (tmp_path / "config.toml").write_text("difficulty = 1\nproblems_required = 5\n")
    (tmp_path / "config.local.toml").write_text("problems_required = 2\nunknown = 1\n")
    cfg = load_config(tmp_path)
    assert cfg.difficulty == 1
    assert cfg.problems_required == 2


def test_config_rejects_bad_difficulty(tmp_path):
    (tmp_path / "config.toml").write_text("difficulty = 9\n")
    with pytest.raises(ValueError):
        load_config(tmp_path)
