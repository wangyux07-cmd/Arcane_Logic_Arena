from abc import ABC, abstractmethod
from collections import namedtuple

# Defines the structure for actions that AI agents can return.
# command: 'MOVE', 'FIREBALL', 'BLINK', 'MEDITATE', 'WAIT'
# params: A tuple of parameters, e.g., (target_x, target_y) for FIREBALL
Action = namedtuple('Action', ['command', 'params'])

class BaseWizard(ABC):
    """
    Abstract base class for all AI wizard implementations.
    Every wizard must implement the 'act' method, which takes the current
    game state (observation) and returns an Action.
    """
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def act(self, observation: dict) -> Action:
        """
        Determines the wizard's next action based on the game state.

        Args:
            observation: A dictionary representing the current state of the arena,
                         including positions of mages, projectiles, etc.

        Returns:
            An Action namedtuple containing the command and its parameters.
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"
