import math
from .base_wizard import BaseWizard, Action

# ------------------ State Pattern Implementation ------------------

class State:
    """Abstract base class for a state in the FSM."""
    def execute(self, wizard, observation: dict) -> Action:
        """Executes the state's logic and returns an action."""
        raise NotImplementedError

    def _get_my_mage(self, wizard_name: str, observation: dict):
        """Helper to find the wizard's own data from the observation."""
        for mage in observation['mages']:
            if mage['name'] == wizard_name:
                return mage
        return None

    def _get_enemy_mage(self, wizard_name: str, observation: dict):
        """Helper to find the enemy's data from the observation."""
        for mage in observation['mages']:
            if mage['name'] != wizard_name:
                return mage
        return None
    
    def _distance(self, x1, y1, x2, y2):
        """Helper to calculate Euclidean distance."""
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

class IdleState(State):
    """The wizard is observing, ready to transition to another state."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        my_mage = self._get_my_mage(wizard.name, observation)
        enemy_mage = self._get_enemy_mage(wizard.name, observation)

        if not my_mage or not enemy_mage:
            return Action('WAIT', None)

        # 1. High-Priority Evade Triggers
        # A. Evade if health has decreased since last frame
        last_hp = wizard.last_known_hp.get(my_mage['name'], my_mage['hp'])
        if my_mage['hp'] < last_hp:
            wizard.transition_to(wizard.evade_state)
            return wizard.evade_state.execute(wizard, observation)

        # B. Evade if a projectile is too close
        for proj in observation['projectiles']:
            if proj['owner'] != my_mage['name']:
                dist_to_proj = self._distance(my_mage['x'], my_mage['y'], proj['x'], proj['y'])
                if dist_to_proj < 100:
                    wizard.transition_to(wizard.evade_state)
                    return wizard.evade_state.execute(wizard, observation)
        
        # 2. Priority: Recover if MP is too low, by first retreating
        if my_mage['mp'] < 10:
            wizard.transition_to(wizard.retreat_state)
            return wizard.retreat_state.execute(wizard, observation)
        
        # 3. Priority: Attack if MP is sufficient and enemy is in range
        if my_mage['mp'] > 30 and self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y']) < 400:
            wizard.transition_to(wizard.attack_state)
            return wizard.attack_state.execute(wizard, observation)
            
        # Default action: wait
        return Action('WAIT', None)

class AttackState(State):
    """The wizard is actively attacking the enemy."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        my_mage = self._get_my_mage(wizard.name, observation)
        enemy_mage = self._get_enemy_mage(wizard.name, observation)

        # Transition out if conditions change
        if my_mage['hp'] < 20:
            wizard.transition_to(wizard.evade_state)
            return wizard.evade_state.execute(wizard, observation)
        if my_mage['mp'] < 30: # Stop attacking if MP drops below threshold
            wizard.transition_to(wizard.idle_state)
            return wizard.idle_state.execute(wizard, observation)
            
        # Action: Fireball at the enemy's current position (simple prediction)
        target_pos = (enemy_mage['x'], enemy_mage['y'])
        return Action('FIREBALL', target_pos)

class EvadeState(State):
    """The wizard is evading danger."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        my_mage = self._get_my_mage(wizard.name, observation)
        
        # Simple evade: blink to a semi-random safe position
        # A better implementation would check for safe zones
        new_x, new_y = my_mage['x'] + 50, my_mage['y'] + 50
        
        # Transition back to idle after evading
        wizard.transition_to(wizard.idle_state)
        return Action('BLINK', (new_x, new_y))

class RecoverState(State):
    """The wizard is recovering MP by meditating."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        my_mage = self._get_my_mage(wizard.name, observation)

        # Transition out once MP is recovered
        if my_mage['mp'] > 40:
            wizard.transition_to(wizard.idle_state)
            return wizard.idle_state.execute(wizard, observation)
        
        return Action('MEDITATE', None)

class RetreatState(State):
    """The wizard is retreating to a safe distance before recovering."""
    def __init__(self):
        self.target_pos = None

    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        my_mage = self._get_my_mage(wizard.name, observation)
        enemy_mage = self._get_enemy_mage(wizard.name, observation)

        # If we haven't decided where to retreat to, calculate it.
        if self.target_pos is None:
            direction_x = my_mage['x'] - enemy_mage['x']
            direction_y = my_mage['y'] - enemy_mage['y']
            distance = self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y'])
            
            # Normalize the direction vector
            if distance > 0:
                direction_x /= distance
                direction_y /= distance

            # Retreat to a point 300 units away from the current position, opposite the enemy
            retreat_distance = 300
            self.target_pos = (
                my_mage['x'] + direction_x * retreat_distance,
                my_mage['y'] + direction_y * retreat_distance
            )

            # Clamp to screen bounds
            self.target_pos = (
                max(50, min(observation['width'] - 50, self.target_pos[0])),
                max(50, min(observation['height'] - 50, self.target_pos[1]))
            )

        # Check if we've arrived at the retreat point
        if self._distance(my_mage['x'], my_mage['y'], self.target_pos[0], self.target_pos[1]) < 20:
            self.target_pos = None # Reset for next time
            wizard.transition_to(wizard.recover_state)
            return wizard.recover_state.execute(wizard, observation)

        # Move towards the target position
        return Action('BLINK', self.target_pos)

# ------------------ FSM Wizard Implementation ------------------

class FSMWizard(BaseWizard):
    """
    A wizard that uses a Finite State Machine to decide its actions.
    It transitions between states (Idle, Attack, Evade, Recover) based
    on the current game observation.
    """
    def __init__(self, name):
        super().__init__(name)
        # Initialize all possible states
        self.idle_state = IdleState()
        self.attack_state = AttackState()
        self.evade_state = EvadeState()
        self.recover_state = RecoverState()
        self.retreat_state = RetreatState()
        
        # Set the initial state
        self.current_state = self.idle_state
        self.current_state_name = "Idle"
        self.last_known_hp = {}

    def transition_to(self, new_state: State):
        """Changes the current state of the wizard."""
        self.current_state_name = new_state.__class__.__name__.replace("State", "")
        self.current_state = new_state

    def act(self, observation: dict) -> Action:
        """
        Delegates the action decision to the current state.
        The state's execute method will handle logic and transitions.
        """
        # Update last known HP before acting
        my_mage = self.current_state._get_my_mage(self.name, observation)
        if my_mage:
            self.last_known_hp[self.name] = my_mage['hp']

        return self.current_state.execute(self, observation)

    def get_debug_info(self, observation: dict) -> dict:
        """Returns the wizard's current plan for rendering."""
        my_mage = self.current_state._get_my_mage(self.name, observation)
        enemy_mage = self.current_state._get_enemy_mage(self.name, observation)
        if not my_mage or not enemy_mage:
            return {}

        plan = {}
        state_name = self.current_state.__class__.__name__

        if state_name == "AttackState":
            plan = {
                'type': 'attack',
                'target': (enemy_mage['x'], enemy_mage['y'])
            }
        elif state_name == "EvadeState":
             # Re-calculate the evade destination for visualization
            new_pos = (my_mage['x'] + 50, my_mage['y'] + 50)
            plan = {
                'type': 'evade',
                'target': new_pos
            }
        
        return {'plan': plan}
