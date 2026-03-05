import csv
import os
import sys
from tqdm import tqdm

# Add project root to Python path to allow imports from other modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import MagicArena, Mage
from agents.fsm_wizard import FSMWizard
from agents.heuristic_wizard import HeuristicWizard

def run_tournament(num_games=100, log_file='logs/tournament_results.csv'):
    """
    Runs a tournament between the FSMWizard and the HeuristicWizard
    and logs the results to a CSV file.
    """
    # Create log file and write header if it doesn't exist
    file_exists = os.path.isfile(log_file)
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['winner_name', 'winner_type', 'loser_name', 'loser_type', 
                             'match_duration_ticks', 'winner_hp', 'winner_mp', 'loser_hp', 'loser_mp'])

    print(f"Running tournament of {num_games} games...")
    
    for i in tqdm(range(num_games)):
        # Initialize arena and mages for each game
        arena = MagicArena(800, 600, headless=True)
        
        # Alternate starting positions
        if i % 2 == 0:
            mage1 = FSMWizard("FSM_Gandalf")
            mage2 = HeuristicWizard("Heuristic_Saruman")
            mage_objects = [Mage(mage1.name, 100, 300), Mage(mage2.name, 700, 300)]
        else:
            mage1 = HeuristicWizard("Heuristic_Gandalf")
            mage2 = FSMWizard("FSM_Saruman")
            mage_objects = [Mage(mage1.name, 100, 300), Mage(mage2.name, 700, 300)]
            
        arena.add_mage(mage_objects[0])
        arena.add_mage(mage_objects[1])
        wizards = {mage1.name: mage1, mage2.name: mage2}

        tick_counter = 0
        max_ticks = 5000 # Max game duration to prevent infinite loops

        # Main game loop
        while not arena.game_over and tick_counter < max_ticks:
            observation = arena.get_game_state()
            
            actions = {}
            for mage_name, wizard in wizards.items():
                actions[mage_name] = wizard.act(observation)
                
            arena.step(actions)
            tick_counter += 1

        # Log the result
        log_game_result(arena, wizards, tick_counter, log_file)

    print(f"Tournament finished. Results logged to {log_file}")

def log_game_result(arena, wizards, duration, log_file):
    """Appends the result of a single game to the log file."""
    state = arena.get_game_state()
    mages_state = {m['name']: m for m in state['mages']}

    winner, loser = None, None
    
    # Identify winner and loser
    for mage_obj in arena.mages:
        if mage_obj.hp > 0:
            winner_name = mage_obj.name
            winner = (winner_name, wizards[winner_name].__class__.__name__)
        else:
            loser_name = mage_obj.name
            loser = (loser_name, wizards[loser_name].__class__.__name__)
    
    # Handle draws or games that timed out
    if not winner or not loser:
        mage1 = arena.mages[0]
        mage2 = arena.mages[1]
        if mage1.hp > mage2.hp:
            winner_name, loser_name = mage1.name, mage2.name
        else:
            winner_name, loser_name = mage2.name, mage1.name
        winner = (winner_name, wizards[winner_name].__class__.__name__)
        loser = (loser_name, wizards[loser_name].__class__.__name__)


    winner_state = mages_state[winner[0]]
    loser_state = mages_state[loser[0]]

    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            winner[0], winner[1], loser[0], loser[1], duration,
            winner_state['hp'], winner_state['mp'],
            loser_state['hp'], loser_state['mp']
        ])

if __name__ == '__main__':
    run_tournament(num_games=100)