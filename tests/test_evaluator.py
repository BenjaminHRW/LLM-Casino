from poker.cards import parse_cards
from poker.evaluator import evaluate_five, evaluate_hand


def _rank(codes: str):
    return evaluate_five(parse_cards(codes.split()))


def test_category_order() -> None:
    royal = _rank("As Ks Qs Js Ts")
    quads = _rank("Ah Ad Ac As 9d")
    boat = _rank("Ah Ad Ac Ks Kd")
    flush = _rank("Ah Kh 9h 5h 2h")
    straight = _rank("9h 8d 7c 6s 5h")
    trips = _rank("9h 9d 9c As Kd")
    two = _rank("9h 9d 5c 5s Ah")
    pair = _rank("9h 9d As Kd Qc")
    high = _rank("Ah Kd 9c 5s 2d")
    ordered = [high, pair, two, trips, straight, flush, boat, quads, royal]
    assert ordered == sorted(ordered)
    assert royal.name == "Royal Flush"
    assert "Wheel" not in _rank("Ah 5h 4d 3c 2s").name
    assert _rank("Ah 5h 4d 3c 2s").name == "Straight, Five high"


def test_wheel_loses_to_six_high() -> None:
    wheel = _rank("Ah 2d 3c 4s 5h")
    six = _rank("6h 2d 3c 4s 5h")
    assert six > wheel


def test_seven_card_picks_best_five() -> None:
    # 2-6 of spades plus junk and an offsuit 8: best is 6-high straight flush
    cards = parse_cards("2s 3s 4s 5s 6s 7d 8d".split())
    rank = evaluate_hand(cards)
    assert rank.category == 8
    assert rank.score[1] == 6


def test_full_house_kickers() -> None:
    aces_over = _rank("Ah Ad Ac Kd Ks")
    kings_over = _rank("Ah Ad Kh Kd Kc")
    assert aces_over > kings_over


def test_pair_kicker_from_seven_cards() -> None:
    board = parse_cards("Ac 9c Ah 5s Kd".split())
    vega = evaluate_hand(parse_cards("Th 7c".split()) + board)
    orion = evaluate_hand(parse_cards("6c 2c".split()) + board)
    assert vega.name.startswith("Pair of Aces")
    assert orion.name.startswith("Pair of Aces")
    assert vega > orion
