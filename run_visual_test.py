from core.engine import MagicArena, Mage
from agents.fsm_wizard import FSMWizard
from agents.heuristic_wizard import HeuristicWizard

def main():
    """
    Sets up and runs a single, rendered match between two AI wizards
    for visual testing and debugging.
    """
    # Initialize the arena in non-headless mode
    arena = MagicArena(1280, 720, headless=False)
    
    # Create wizards (the AI)
    fsm_wizard = FSMWizard("FSM_Merlin")
    heuristic_wizard = HeuristicWizard("Heuristic_Morgana")
    wizards = {fsm_wizard.name: fsm_wizard, heuristic_wizard.name: heuristic_wizard}
    
    # Create mages (the in-game entities) and add them to the arena
    mage1 = Mage(fsm_wizard.name, 200, 360)
    mage2 = Mage(heuristic_wizard.name, 1080, 360)
    
    arena.add_mage(mage1)
    arena.add_mage(mage2)
    
    # Start the interactive simulation
    arena.run_interactive(wizards)

if __name__ == '__main__':
    main()
