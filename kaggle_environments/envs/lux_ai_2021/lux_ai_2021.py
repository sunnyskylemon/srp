import json
import math
import random
from os import path
from .agents import agents as all_agents
from subprocess import Popen, PIPE, STDOUT
import time
import sys
import atexit
from .test_agents.python.lux.game import Game


dimension_process = None
game_state = Game()
def cleanup_dimensions():
    global dimension_process
    if dimension_process is not None:
        dimension_process.kill()

def interpreter(state, env):
    global dimension_process, game_state
    player1 = state[0]
    player2 = state[1]

    ### 1.1: Initialize dimensions in the background within the orchestrator if we haven't already ###
    if dimension_process is None:
        # dimension_process = Popen(["ts-node", "-P", path.abspath(path.join(dir_path, "dimensions/tsconfig.json")), path.abspath(path.join(dir_path, "dimensions/run.ts"))], stdin=PIPE, stdout=PIPE)
        dimension_process = Popen(["node", path.abspath(path.join(dir_path, "dimensions/main.js"))], stdin=PIPE, stdout=PIPE)
        atexit.register(cleanup_dimensions)

    ### TODO: check if process is still running, handle failure cases here

    ### 1.2: Initialize a blank state game if new episode is starting ###
    if env.done:
        if "seed" in env.configuration:
            seed = env.configuration["seed"]
        else:
            seed = math.floor(random.random() * 1e9);
            env.configuration["seed"] = seed
        initiate = {
            "type": "start",
            "agent_names": [], # unsure if this is provided?
            "config": env.configuration
        }
        dimension_process.stdin.write((json.dumps(initiate) + "\n").encode())
        dimension_process.stdin.flush()
        agent1res = json.loads(dimension_process.stdout.readline())
        agent2res = json.loads(dimension_process.stdout.readline())
        
        player1.observation.player = 0
        player2.observation.player = 1
        player1.observation.updates = agent1res
        player2.observation.updates = agent2res

        game_state = Game()
        game_state._initialize(agent1res)

        return state
    
    ### 2. : Pass in actions (json representation along with id of who made that action), agent information (id, status) to dimensions via stdin
    dimension_process.stdin.write((json.dumps(state) + "\n").encode())
    dimension_process.stdin.flush()


    ### 3.1 : Receive and parse the observations returned by dimensions via stdout
    agent1res = json.loads(dimension_process.stdout.readline())
    agent2res = json.loads(dimension_process.stdout.readline())
    game_state._update(agent1res)

    match_status = json.loads(dimension_process.stdout.readline())

    ### 3.2 : Send observations to each agent through here. Like dimensions, first observation can include initialization stuff, then we do the looping

    player1.observation.updates = agent1res
    player2.observation.updates = agent2res

    player1.observation.player = 0
    player2.observation.player = 1

    ### 3.3 : handle rewards
    # reward here is defined as the sum of number of city tiles
    player1.reward = sum([len(v.citytiles) for k, v in game_state.players[0].cities.items()])
    player2.reward = sum([len(v.citytiles) for k, v in game_state.players[1].cities.items()])
    player1.observation.reward = int(player1.reward)
    player2.observation.reward = int(player2.reward)

    ### 3.4 Handle finished match status
    if match_status["status"] == "finished":
        player1.status = "DONE"
        player2.status = "DONE"
    return state


def renderer(state, env):
    sign_names = ["Rock", "Paper", "Scissors", "Spock", "Lizard"]
    rounds_played = len(env.steps)
    board = ""

    # This line prints results each round, good for debugging
    for i in range(1, rounds_played):
        step = env.steps[i]
        right_move = step[0].observation.lastOpponentAction
        left_move = step[1].observation.lastOpponentAction
        board += f"Round {i}: {sign_names[left_move]} vs {sign_names[right_move]}, Score: {step[0].reward} to {step[1].reward}\n"

    board += f"Game ended on round {rounds_played - 1}, final score: {state[0].reward} to {state[0].reward}\n"
    return board


dir_path = path.dirname(__file__)
json_path = path.abspath(path.join(dir_path, "lux_ai_2021.json"))
with open(json_path) as json_file:
    specification = json.load(json_file)


def html_renderer():
    html_path = path.abspath(path.join(dir_path, "index.html"))
    return ("html_path", html_path)

agents = all_agents