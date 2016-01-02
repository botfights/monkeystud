import pytest
import mock

@pytest.mark.unit
def test_play_hand_valid_argument():
    from monkeystud import play_hand, make_player
    player1 = make_player('p_1', 'p_random', False)
    history_ref = None

    def get_play(history):
        history_ref = history
        return 'Z'

    player1.get_play = get_play
    player2 = make_player('p_2', 'p_random', False)
    try:
        play_hand([player1, player2], 10, False)
    finally:
        player1.done()
        player2.done()

    assert player1.played is True
    assert player2.played is True


@pytest.mark.unit
def test_play_game_ante():
    from monkeystud import play_game, make_player
    player1 = make_player('p_1', 'p_random', False)
    history_ref = None

    def get_play(history):
        history_ref = history
        return 'C'

    player1.get_play = get_play
    player2 = make_player('p_2', 'p_random', False)


    try:
        with mock.patch('monkeystud.logging') as l:
            play_game([player1, player2], False)
    finally:
        player1.done()
        player2.done()

    antes = []
    for call in l.debug.mock_calls:
        data = call[1][0]
        if 'antes' in data:
            antes.append(int(data.split()[-1]))

    assert antes[0] < antes[-1]
    assert player1.played is True
    assert player2.played is True


@pytest.mark.unit
def test_make_player_subprocess():
    from monkeystud import PlayerProcess
    from monkeystud import PlayerMemory
    from monkeystud import make_player

    player1 = make_player('p_1', 'p_random', False, subprocess=True)
    player2 = make_player('p_2', 'p_random', False, subprocess=False)
    player1.done()
    player2.done()

    assert isinstance(player1, PlayerProcess)
    assert isinstance(player2, PlayerMemory)


@pytest.mark.unit
def test_player_name():
    from monkeystud import BasePlayer

    p1 = BasePlayer(1, '/foo/bar/baz/', 0, True)
    p2 = BasePlayer(1, 'bar/baz/', 0, True)
    p3 = BasePlayer(1, 'bar/baz', 0, True)
    p4 = BasePlayer(1, 'baz/', 0, True)
    p5 = BasePlayer(1, 'baz', 0, True)

    players = [p1, p2, p3, p4, p5]

    for player in players:
        assert player.playername == 'baz'
