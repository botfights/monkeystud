# monkeystud.py -- MonkeyStud, a poker variant for bots

# see README.md for more dox

import os, random, sys, itertools, logging, imp, time, itertools, getopt
from multiprocessing import Process, Queue as MPQueue
import Queue
import click
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

CHIPS_START    = 1000               # each player starts with 1000 chips
MAX_SEATS      = 8                  # maximum seats at a table

RANKS          = 8                  # duece through nine
SUITS          = 4                  # clubs, diamonds, hearts, spades
INVALID_CARD   = 17 << 3
HIGH           = 0                  # high card
PAIR           = 1                  # one pair
STR            = 2                  # straight
FLUSH          = 3                  # flush
TRIP           = 4                  # three of a kind
STRF           = 5                  # straight flush


def make_card(r, s):
    return (r << 3) | s


def rank_suit(c):
    return c >> 3, c & 7


def rank_str(r):
    return '23456789'[r]


def suit_str(s):
    return 'cdhs'[s]


def card_str(a):
    if INVALID_CARD == a:
        return 'xx'
    return "%s%s" % (rank_str(a >> 3), suit_str(a & 7))


def str_to_card(s):
    if 'xx' == s:
        return INVALID_CARD
    return make_card(ord(s[0]) - ord('2'), {'c': 0, 'd': 1, 'h': 2, 's': 3}[s[1]])


def str_to_hand(s):
    h = []
    for i in s.split(','):
        h.append(str_to_card(i.strip()))
    return h


def hand_str(h):
    return ','.join(map(lambda x : card_str(x), h))


def hand_value_class(x):
    return x >> 28


def hand_value_str(x):
    c = x >> 28
    if HIGH == c:
        return 'high card (%s, %s, %s)' % \
                (rank_str((x >> 8) & 15), \
                rank_str((x >> 4) & 15), rank_str(x & 15))
    if PAIR == c:
        return 'pair of %s\'s (%s, %s, %s)' % \
                (rank_str((x >> 24) & 15), rank_str((x >> 8) & 15), \
                rank_str((x >> 4) & 15), rank_str(x & 15))
    if STR == c:
        return 'straight to the %s' % rank_str((x >> 24) & 15)
    if FLUSH == c:
        return 'flush (%s, %s, %s)' % \
                (rank_str((x >> 8) & 15), \
                rank_str((x >> 4) & 15), rank_str(x & 15))
    if TRIP == c:
        return 'trip %s\'s' % rank_str((x >> 24) & 15)
    if STRF == c:
        return 'straight flush to the %s' % rank_str((x >> 24) & 15)


def new_deck():
    d = []
    for i in range(SUITS):
        for j in range(RANKS):
            d.append(make_card(j, i))
    return d


def shuffle(d):
    random.shuffle(d)
    return d


def hand_value(h):
    "classify three card hand into uint32 that supports equality and greater than"
    ar = h[0] >> 3
    br = h[1] >> 3
    cr = h[2] >> 3
    ah = h[0] & 7
    bh = h[1] & 7
    ch = h[2] & 7
    if ar < br:
        if br < cr:
            h, m, l = cr, br, ar
        elif ar < cr:
            h, m, l = br, cr, ar
        else:
            h, m, l = br, ar, cr
    else:
        if ar < cr:
            h, m, l = cr, ar, br
        elif br < cr:
            h, m, l = ar, cr, br
        else:
            h, m, l = ar, br, cr
    if h == m:
        if m == l:
            x = (TRIP << 28) | (h << 24)
        else:
            x = (PAIR << 28) | (h << 24) | (h << 8) | (m << 4) | l
    elif m == l:
        x = (PAIR << 28) | (m << 24) | (h << 8) | (m << 4) | l
    elif (h == (m + 1)) and (h == (l + 2)):
        if (ah == bh) and (ah == ch):
            x = (STRF << 28) | (h << 24)
        else:
            x = (STR << 28) | (h << 24)
    elif (ah == bh) and (ah == ch):
        x = (FLUSH << 28) | (h << 8) | (m << 4) | l
    else:
        x = (HIGH << 28) | (h << 8) | (m << 4) | l
    return x


def best_hand_value(h):
    best = None
    for i in itertools.combinations(h, 3):
        x = hand_value(i)
        if None == best or x > best:
            best = x
    return best


class BasePlayer(object):
    def __init__(self, player_id, dirname, chips, catch_exceptions):
        self.player_id = player_id
        self.chips = chips
        self.elapsed = 0.0
        self.calls = 0
        self.catch_exceptions = catch_exceptions
        self.dirname = dirname

        if dirname.endswith('/'):
            dirname = dirname[:-1]

        self.playername = dirname.split('/')[-1]

    def import_bot(self):
        name = 'bot'
        func = None
        (f, filename, data) = imp.find_module(name, [self.dirname, ])
        m = None
        try:
            m = imp.load_module(name, f, filename, data)
        except ImportError:
            logging.error("Couldn't import bot.py from %s" % self.dirname)

        if None == m or not hasattr(m, 'play'):
            logging.error(
                '%s has no function "play"; ignoring ...' % self.dirname
            )
        else:
            func = getattr(m, 'play')

        return func

    def get_play(self, x):
        return call_player(
            self,
            (self.player_id, self.hand, x),
            self.catch_exceptions
        )


    def done(self):
        pass

    def is_alive(self):
        return True

class PlayerMemory(BasePlayer):
    def __init__(self, player_id, dirname, chips, catch_exceptions):
        BasePlayer.__init__(self, player_id, dirname, chips, catch_exceptions)
        self.play = self.import_bot()

class PlayerProcess(BasePlayer, Process):
    def __init__(self, player_id, dirname, chips, catch_exceptions):
        Process.__init__(self)
        BasePlayer.__init__(self, player_id, dirname, chips, catch_exceptions)

        self.send_queue = MPQueue()
        self.recv_queue = MPQueue()

    def play(self, player_id, hand, history):
        self.send_queue.put((player_id, hand, history))
        result = self.recv_queue.get()
        return result

    def done(self):
        self.send_queue.put('QUIT')

    def run(self):
        result = None

        try:
            func = self.import_bot()
        except:
            logging.error('caught exception "%s" loading %s' % \
                          (sys.exc_info()[1], self.dirname))

            if not self.catch_exceptions:
                raise

        if func is not None:
            while True:
                data = self.send_queue.get()
                if data == "QUIT":
                    break
                try:
                    result = func(*data)
                except:
                    logging.warn(
                        'caught exception "%s" calling %s (%s)' % (
                            sys.exc_info()[1], self.player_id, self.playername
                        )
                    )
                    if not self.catch_exceptions:
                        raise

                self.recv_queue.put(result)

def call_player(player, args, catch_exceptions):
    start = time.clock()
    result = None

    try:
        result = player.play(*args)
    except KeyboardInterrupt:
        raise
    except:
        logging.warn('caught exception "%s" calling %s (%s)'
                     % (sys.exc_info()[1], player.player_id, player.playername))
        if not catch_exceptions:
            raise
    elapsed = time.clock() - start
    player.elapsed += elapsed
    player.calls += 1
    return result


def make_player(player_id, dirname, catch_exceptions, subprocess=True):
    if subprocess is True:
        p = PlayerProcess(player_id, dirname, CHIPS_START, catch_exceptions)
        p.start()
    else:
        p = PlayerMemory(player_id, dirname, CHIPS_START, catch_exceptions)
    return p


def serialize_history(history):
    t = ''
    for i in history:
        if 0 != len(t):
            t += ' '
        t += '%s:%s:%s' % (i[0], i[1], i[2])
    return t


def play_hand(players, catch_exceptions, ante_amount, kibitzers=None):
    """
    play a single hand of monkeystud
    """
    # sit
    #
    history = []
    random.shuffle(players)
    d = new_deck()
    random.shuffle(d)
    player_count = 0
    for seat, i in enumerate(players):
        if 0 == i.chips:
            i.folded = True
        else:
            player_count += 1
            i.hand = []
            i.paid = 0
            i.folded = False
            history.append((i.player_id, 'S', i.chips))
            logging.debug('ACTION\t%s sits down at seat %d with %d' % \
                    (i.player_id, seat, i.chips))

    # state machine
    #
    pot = 0
    for state in (0, 1, 2, 3, 4):

        # bail out early
        #
        if 1 == player_count:
            break

        # ante
        #
        if 0 == state:

            # find the ante amount
            #
            ante = ante_amount
            for i in players:
                if 0 == i.chips:
                    continue
                ante = min(ante, i.chips)
            for i in players:
                if 0 == i.chips:
                    continue
                pot += ante
                i.chips -= ante
                i.paid += ante
                history.append((i.player_id, 'A', ante))
                logging.debug('ACTION\t%s antes %d' % (i.player_id, ante))

        # cards
        #
        if state in (1, 2, 3, 4):
            for i in players:
                if i.folded:
                    continue
                card = d.pop()
                i.hand.append(card)
                if 1 == state:
                    history.append((i.player_id, 'D', 'xx'))
                    logging.debug('ACTION\t%s is dealt %s down' % \
                            (i.player_id, card_str(card)))
                else:
                    history.append((i.player_id, 'U', card_str(card)))
                    logging.debug('ACTION\t%s is dealt %s up' % \
                            (i.player_id, card_str(card)))

        # betting rounds
        #
        if state in (2, 3, 4):
            # keep asking players for their bet until
            # there's no new action
            #
            raised_to = 0
            for i in players:
                i.paid = 0
                i.played = False
            action = None
            last_action = None
            while 1:
                # advance the action
                #
                while 1:
                    if None == action:
                        action = 0
                    else:
                        action += 1
                        if action == len(players):
                            action = 0
                    if not players[action].folded:
                        break

                if action == last_action:
                    break

                # no new action?
                #
                if players[action].played and players[action].paid == raised_to:
                    break

                # get their play
                #
                x = players[action].get_play(serialize_history(history))

                if not x in ('F', 'C', 'B'):
                    x = 'F'
                players[action].played = True

                # fold?
                #
                if 'F' == x:

                    # folding when there is no bet? make it a call
                    #
                    if players[action].paid == raised_to:
                        x = 'C'
                    else:
                        players[action].folded = True
                        history.append((players[action].player_id, 'F', 0))
                        logging.debug('ACTION\t%s folds' % players[action].player_id)
                        player_count -= 1
                        if 1 == player_count:
                            break

                # call?
                #
                if 'C' == x:
                    to_call = raised_to - players[action].paid
                    pot += to_call
                    players[action].paid += to_call
                    players[action].chips -= to_call
                    history.append((players[action].player_id, 'C', to_call))
                    logging.debug('ACTION\t%s calls %d' % \
                            (players[action].player_id, to_call))

                # bet?
                #
                if 'B' == x:
                    to_call = raised_to - players[action].paid
                    if 0 != to_call:
                        pot += to_call
                        players[action].paid += to_call
                        players[action].chips -= to_call
                        history.append((players[action].player_id, 'C', \
                                to_call))
                        logging.debug('ACTION\t%s calls %d' % \
                                (players[action].player_id, to_call))

                    # figure out the maximum raise
                    #
                    the_raise = pot
                    for i in players:
                        if i.folded:
                            continue
                        x = i.chips - (raised_to - i.paid)
                        if x < the_raise:
                            the_raise = x

                    if 0 != the_raise:
                        raised_to += the_raise
                        pot += the_raise
                        players[action].paid += the_raise
                        players[action].chips -= the_raise
                        history.append((players[action].player_id, 'B', \
                                the_raise))
                        logging.debug('ACTION\t%s bets %d' % \
                                (players[action].player_id, the_raise))
                        last_action = action

    # end of hand, figure out who won
    #
    remaining_players = []
    for i in players:
        if not i.folded:
            remaining_players.append(i)

    # only one player left?
    #
    if 1 == len(remaining_players):
        winners = remaining_players

    # nope, let's reveal and find the best hand
    #
    else:
        for i in remaining_players:
            history.append((i.player_id, 'R', hand_str(i.hand)))
            logging.debug('ACTION\t%s reveals %s -- %s' % (i.player_id, hand_str(i.hand), \
                          hand_value_str(best_hand_value(i.hand))))
        best_so_far = [0, []]
        for i in remaining_players:
            best_hand = best_hand_value(i.hand)
            if best_hand > best_so_far[0]:
                best_so_far = [best_hand, [i, ]]
            elif best_hand == best_so_far[0]:
                best_so_far[1].append(i)
        winners = best_so_far[1]

    # divide the pot
    #
    chips_per_winner = pot // len(winners)
    remainder = pot % len(winners)
    for i in winners:
        i.chips += chips_per_winner
        history.append((i.player_id, 'W', chips_per_winner))
        if 1 == len(winners):
            logging.debug('ACTION\t%s wins %d' % (i.player_id, chips_per_winner))
        else:
            logging.debug('ACTION\t%s wins %d in split' % (i.player_id, chips_per_winner))

    # give remainder to random winner
    #
    if 0 != remainder:
        lucky_player = random.choice(winners)
        lucky_player.chips += remainder
        history.append((lucky_player.player_id, 'Z', remainder))
        logging.debug('ACTION\t%s wins remainder %s' % \
                (lucky_player.player_id, remainder))

    # show everyone what happened (including just observers)
    #
    serialized_history = serialize_history(history)
    logging.debug('HISTORY\t%s' % serialized_history)
    for i in players:
        i.get_play(serialized_history)
    if None != kibitzers:
        for i in kibitzers:
            i.hand = None
            i.get_play(serialized_history)

    # all done.
    #
    return


def play_game(players, catch_exceptions, kibitzers=None):
    """
    play a game with chips, return winner
    """
    for i in players:
        i.chips = CHIPS_START
    ante_amount = 1

    while 1:
        t = ''
        winner = None
        for i in players:
            t += '%s:%s:%d ' % (i.player_id, i.playername, i.chips)
            if i.chips == (len(players) * CHIPS_START):
                winner = i
        logging.debug('CHIPS\t%s' % t)
        if None != winner:
            return winner

        play_hand(players, catch_exceptions, ante_amount, kibitzers)
        ante_amount += 1


def play_tournament(games, players, catch_exceptions):
    """
    play many games, return map of player_id to wins
    """
    for i in players:
        i.wins = 0

    for i in range(games):
        kibitzers = None
        if MAX_SEATS < len(players):
            table = random.sample(players, MAX_SEATS)
            logging.info(
                'TABLE\t%s' % ' '.join(map(lambda x: x.playername, table))
            )
            kibitzers = []
            seated = {}
            for j in table:
                seated[j.player_id] = 1
            for j in players:
                if not j.player_id in seated:
                    kibitzers.append(j)
        else:
            table = players

        # Start the players back up
        for p in table:
            if p.is_alive() is False:
                p.start()

        winner = play_game(table, catch_exceptions, kibitzers)
        winner.wins += 1
        t = ''
        players.sort(key = lambda x : x.wins,reverse = True)
        for j in players:
            t += '%s:%d\t' % (j.playername, j.wins)
        logging.info('BOTFIGHT\t%d\t%d\t%s' % (i, games, t))

    for i in players:
        i.done()

def verify_player(max_time, playername):
    catch_exceptions = True
    logging.info('verifying %s ...' % playername)
    p1 = make_player(1, playername, catch_exceptions)
    if None == p1.play:
        logging.info('verification FAILED. import failed.')
        return 3
    p2 = make_player(2, 'p_random', catch_exceptions)
    logging.info('playing 100 games against random ...')
    play_tournament(100, [p1, p2], catch_exceptions)
    logging.info('%s: %f seconds, %d calls' % (playername, p1.elapsed, \
            p1.calls))
    logging.info('random: %f seconds, %d calls' % (p2.elapsed, p2.calls))
    factor = (p1.elapsed / p1.calls) / (p2.elapsed / p2.calls)
    logging.info('player is %.1fx slower than random' % factor)
    if max_time < factor:
        logging.info('verification FAILED. max_time is %.1f.' % max_time)
        return 1
    logging.info('verification success.')
    return 0
