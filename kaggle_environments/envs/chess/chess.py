import random
import json
from os import path
from collections import defaultdict

from Chessnut import Game

ERROR = "ERROR"
DONE = "DONE"
INACTIVE = "INACTIVE"
ACTIVE = "ACTIVE"
WHITE = "white"


def random_agent(obs):
    """
    Selects a random legal move from the board.
    Returns:
    A string representing the chosen move in UCI notation (e.g., "e2e4").
    """
    game = Game(obs.board)
    moves = list(game.get_moves())
    return random.choice(moves)


def king_shuffle_agent(obs):
    """Moves the king pawn and then shuffles the king."""
    game = Game(obs.board)
    moves = list(game.get_moves())

    to_move = ["e7e5", "e2e4", "e8e7", "e7e8", "e1e2", "e2e1"]
    for move in to_move:
        if move in moves:
            return move

    # If no other moves are possible, pick a random legal move (or return None)
    return random.choice(moves) if moves else None


def board_shuffle_agent(obs):
    """Moves the king panw and then shuffles pieces."""
    game = Game(obs.board)
    moves = list(game.get_moves())

    to_move = ["e7e5", "e2e4", "e8e7", "e7e6", "e1e2", "e2e3"]
    for move in to_move:
        if move in moves:
            return move

    # add shuffle moves for knights and bishop
    to_shuffle = [
        "b1c3",
        "c3b1",
        "g1f3",
        "f3g1",
        "b8c6",
        "c6b8",
        "g8f6",
        "f6g8",
        "f1e2",
        "e2f1",
        "f8e7",
        "e7f8",
    ]
    # filter to only shuffle king moves
    for move in moves:
        f1 = move[0]
        f2 = move[2]
        r1 = int(move[1])
        r2 = int(move[3])
        df = abs(ord(f1) - ord(f2))
        dr = abs(r2 - r1)
        if r1 < 3 or r1 > 6:
            continue
        if r2 < 3 or r2 > 6:
            continue
        if dr > 1 or df > 1:
            continue
        if move[2:4] == "e5":
            continue
        if move[2:4] == "e4":
            continue
        to_shuffle.append(move)
    random.shuffle(to_shuffle)
    for move in to_shuffle:
        if move in moves:
            return move

    # If no other moves are possible, pick a random legal move (or return None)
    return random.choice(moves) if moves else None


agents = {
    "random": random_agent,
    "king_shuffle": king_shuffle_agent,
    "board_shuffle": board_shuffle_agent}


def sufficient_material(pieces):
    """Checks if the given pieces are sufficient for checkmate."""
    if pieces['q'] > 0 or pieces['r'] > 0 or pieces['p'] > 0:
        return True
    if pieces['n'] + pieces['b'] >= 3:
        return True
    # TODO: they have to be opposite color bishops
    # b/b or n/b can checkmate, n/n cannot
    if pieces['n'] < 2:
        return True

    return False


def is_insufficient_material(board):
    white_pieces = defaultdict(int)
    black_pieces = defaultdict(int)

    for square in range(64):
        piece = board.get_piece(square)
        if piece:
            if piece.isupper():
                white_pieces[piece.lower()] += 1
            else:
                black_pieces[piece.lower()] += 1

    if not sufficient_material(
            white_pieces) and not sufficient_material(black_pieces):
        return True

    return False


def square_str_to_int(square_str):
    """Converts a square string (e.g., "a2") to an integer index (0-63)."""
    if len(square_str) != 2 or not (
            'a' <= square_str[0] <= 'h' and '1' <= square_str[1] <= '8'):
        raise ValueError("Invalid square string")

    col = ord(square_str[0]) - ord('a')  # Get column index (0-7)
    row = int(square_str[1]) - 1        # Get row index (0-7)
    return row * 8 + col


seen_positions = defaultdict(int)
game_one_complete = False

def interpreter(state, env):
    global seen_positions
    global game_one_complete
    if env.done:
        game_one_complete = False
        seen_positions = defaultdict(int)
        return state

    if state[0].status == ACTIVE and state[1].status == ACTIVE:
        # set up new game
        state[0].observation.mark, state[1].observation.mark = state[1].observation.mark, state[0].observation.mark
        state[0].observation.board = Game().get_fen()
        state[1].observation.board = Game().get_fen()
        state[0].status = ACTIVE if state[0].observation.mark == WHITE else INACTIVE
        state[0].status = ACTIVE if state[0].observation.mark == WHITE else INACTIVE
        return state

    # Isolate the active and inactive agents.
    active = state[0] if state[0].status == ACTIVE else state[1]
    inactive = state[0] if state[0].status == INACTIVE else state[1]
    if active.status != ACTIVE or inactive.status != INACTIVE:
        active.status = DONE if active.status == ACTIVE else active.status
        inactive.status = DONE if inactive.status == INACTIVE else inactive.status
        return state

    # The board is shared, only update the first state.
    board = state[0].observation.board

   # Create a chessnut game object from the FEN string
    game = Game(board)

    # Get the action (move) from the agent
    action = active.action

    # Check if the move is legal
    try:
        game.apply_move(action)
    except BaseException:
        active.status = ERROR
        active.reward = -1
        inactive.status = DONE
        return state
    fen = game.get_fen()
    board_str = fen.split(" ", maxsplit=1)[0]
    seen_positions[board_str] += 1

    # Update the board in the observation
    state[0].observation.board = fen
    state[1].observation.board = fen

    terminal_state = DONE if game_one_complete else ACTIVE
    pawn_or_capture_move_count = int(
        fen.split(" ")[4])  # fen keeps track of this
    # Check for game end conditions
    if pawn_or_capture_move_count == 100 or is_insufficient_material(
            game.board):
        active.status = terminal_state
        inactive.status = terminal_state
        game_one_complete = True
    elif seen_positions[board_str] >= 3 or game.status == Game.STALEMATE:
        active.status = terminal_state 
        inactive.status = terminal_state
        game_one_complete = True
    elif game.status == Game.CHECKMATE:
        active.reward += 1
        active.status = terminal_state
        inactive.status = terminal_state
        game_one_complete = True
    else:
        # Switch turns
        active.status = INACTIVE
        inactive.status = ACTIVE

    return state


def renderer(state, env):
    board_fen = state[0].observation.board
    game = Game(board_fen)
    return game.board


jsonpath = path.abspath(path.join(path.dirname(__file__), "chess.json"))
with open(jsonpath) as f:
    specification = json.load(f)


def html_renderer():
    jspath = path.abspath(path.join(path.dirname(__file__), "chess.js"))
    with open(jspath) as g:
        return g.read()
