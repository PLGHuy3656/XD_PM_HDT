from swiftletcare_ai.counter import LineCounter
from swiftletcare_ai.schemas import Detection

# Horizontal line y=100. Positive side = below the line (y > 100) in image coordinates.
LINE = ((0, 100), (200, 100))
DOWN = [(50, 50), (50, 80), (50, 120), (50, 150)]      # outside -> inside when inside_side=positive
UP = DOWN[::-1]                                         # inside -> outside


def det(tid, x, y):
    return Detection("swiftlet", 0.9, [x - 5, y - 5, x + 5, y + 5], tid)


def run(counter, path, tid=1):
    for i, (x, y) in enumerate(path):
        counter.update([det(tid, x, y)], i)


def test_entry_and_exit_directions():
    c = LineCounter(*LINE, inside_side="positive")
    run(c, DOWN)
    assert (c.entry, c.exit) == (1, 0)
    run(c, UP, tid=2)
    assert (c.entry, c.exit) == (1, 1) and c.net == 0


def test_inside_side_flips_direction():
    c = LineCounter(*LINE, inside_side="negative")
    run(c, DOWN)
    assert (c.entry, c.exit) == (0, 1)


def test_fast_bird_skipping_frames_still_counted():
    c = LineCounter(*LINE)
    run(c, [(50, 20), (50, 180)])           # crosses the line within one step
    assert c.entry == 1


def test_no_count_outside_segment():
    c = LineCounter(*LINE)
    run(c, [(400, 50), (400, 80), (400, 120), (400, 150)])   # crosses the extended line, not the segment
    assert c.entry + c.exit == 0


def test_hovering_near_line_counts_once():
    c = LineCounter(*LINE)
    run(c, [(50, 120), (50, 105), (50, 98), (50, 99), (50, 97), (50, 96)])
    assert c.entry + c.exit == 1


def test_min_hits_ignores_very_new_tracks():
    c = LineCounter(*LINE, min_hits=3)
    run(c, [(50, 80), (50, 120)])           # crossing on the 2nd observation
    assert c.entry + c.exit == 0


def test_center_exactly_on_line_counts_once():
    c = LineCounter(*LINE)
    run(c, [(50, 60), (50, 100), (50, 140), (50, 160)])     # lands exactly on y=100
    assert (c.entry, c.exit) == (1, 0)


def test_touch_line_and_return_counts_nothing():
    c = LineCounter(*LINE)
    run(c, [(50, 60), (50, 100), (50, 70), (50, 50)])
    assert c.entry + c.exit == 0


def test_multiple_birds():
    c = LineCounter(*LINE)
    for i in range(4):
        run(c, [(20 + i * 30, y) for y in (40, 70, 130, 160)], tid=i + 1)
    assert c.entry == 4 and c.net == 4


def test_from_normalized_and_bad_side():
    c = LineCounter.from_normalized(((0.0, 0.5), (1.0, 0.5)), (200, 400, 3))
    assert c.a == (0.0, 100.0) and c.b == (400.0, 100.0)
    try:
        LineCounter((0, 0), (1, 1), inside_side="left")
        assert False
    except ValueError:
        pass