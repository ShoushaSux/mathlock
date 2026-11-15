import random

import pytest
from PIL import Image

from mathlock import stats
from mathlock.config import load_config
from mathlock.gifs import (DEFAULT_DELAY_MS, Look, find_gifs, load_frames, random_look,
                           render, target_count)


def make_gif(path, n_frames=4, size=(200, 100), durations=(50, 120, 0, 80)):
    frames = [Image.new("RGBA", size, (40 * i, 100, 200, 255)) for i in range(n_frames)]
    frames[0].save(path, save_all=True, append_images=frames[1:], loop=0,
                   duration=list(durations)[:n_frames], disposal=2)
    return path


# -- how many GIFs ----------------------------------------------------------
def test_target_count_curve():
    counts = [target_count(w, grace=1, growth=1.6, max_windows=25) for w in range(10)]
    assert counts == [0, 0, 1, 2, 3, 4, 7, 10, 17, 25]


def test_target_count_is_monotonic_and_capped():
    counts = [target_count(w, 2, 2.0, 30) for w in range(40)]
    assert counts == sorted(counts) and max(counts) == 30


def test_target_count_linear_and_disabled():
    assert [target_count(w, 0, 1.0, 10) for w in range(4)] == [0, 1, 2, 3]
    assert target_count(50, 0, 1.6, max_windows=0) == 0


# -- decoding ---------------------------------------------------------------
def test_load_frames_and_delays(tmp_path):
    frames, delays = load_frames(make_gif(tmp_path / "a.gif"), max_size=100)
    assert len(frames) == 4
    assert delays == [50, 120, DEFAULT_DELAY_MS, 80]
    assert all(max(f.size) <= 100 and f.mode == "RGBA" for f in frames)


def test_long_gifs_are_thinned_keeping_total_time(tmp_path):
    path = make_gif(tmp_path / "long.gif", n_frames=10, durations=[100] * 10)
    frames, delays = load_frames(path, max_size=100, max_frames=4)
    assert len(frames) <= 4 and sum(delays) == 1000


def test_load_rejects_non_gif(tmp_path):
    png = tmp_path / "x.gif"
    Image.new("RGB", (4, 4)).save(png, format="PNG")
    with pytest.raises(ValueError):
        load_frames(png, 100)


def test_find_gifs(tmp_path):
    make_gif(tmp_path / "a.gif"); make_gif(tmp_path / "B.GIF")
    (tmp_path / "notes.txt").write_text("hi")
    assert [p.name for p in find_gifs(tmp_path)] == ["B.GIF", "a.gif"]
    assert find_gifs(tmp_path / "missing") == []


# -- random looks -----------------------------------------------------------
def test_random_look_within_bounds():
    rng = random.Random(7)
    looks = [random_look(rng, 120, 360, 45) for _ in range(300)]
    assert all(120 <= l.size <= 360 and -45 <= l.angle <= 45 for l in looks)
    assert len({l.size for l in looks}) > 50 and {l.mirror for l in looks} == {True, False}


def test_render_size_rotation_and_key_color():
    key = (255, 0, 254)
    frames = [Image.new("RGBA", (200, 100), (10, 20, 30, 255))]
    upright = render(frames, Look(size=100, angle=0, mirror=False), key)[0]
    assert upright.size == (100, 50) and upright.mode == "RGB"
    tilted = render(frames, Look(size=100, angle=45, mirror=True), key)[0]
    assert tilted.width > 100 and tilted.height > 50            # expanded to fit
    assert tilted.getpixel((0, 0)) == key                        # empty corner is keyed out
    assert tilted.getpixel((tilted.width // 2, tilted.height // 2)) == (10, 20, 30)


# -- stats / config -----------------------------------------------------------
def test_stats_record_and_total(tmp_path):
    path = tmp_path / "sub" / "stats.jsonl"
    assert stats.total_wrong(path) == 0
    stats.record(stats.Session("t0", "t1", solved=3, wrong=4), path)
    stats.record(stats.Session("t2", "t3", solved=3, wrong=2, escaped=True), path)
    with path.open("a") as fh:
        fh.write("not json\n")
    assert stats.total_wrong(path) == 6


def test_gif_dir_resolved_relative_to_config(tmp_path):
    (tmp_path / "config.toml").write_text('gif_dir = "my_gifs"\n')
    assert load_config(tmp_path).gif_dir == str(tmp_path / "my_gifs")


def test_config_rejects_bad_gif_sizes(tmp_path):
    (tmp_path / "config.toml").write_text("gif_min_size = 400\ngif_max_size = 100\n")
    with pytest.raises(ValueError):
        load_config(tmp_path)
