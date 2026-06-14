from vol_realizada_b3.jumps import jump_variation


def test_jump_variation_non_negative() -> None:
    assert jump_variation(0.01, 0.02) == 0
    assert jump_variation(0.03, 0.02) > 0

