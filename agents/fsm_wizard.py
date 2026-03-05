import math
import random
from .base_wizard import BaseWizard, Action

# ------------------ State Pattern Implementation (Final Refactor) ------------------

class State:
    """A state in the FSM. Now includes MP checks for all actions."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        raise NotImplementedError

    def _get_my_mage(self, wizard_name: str, observation: dict):
        for mage in observation['mages']:
            if mage['name'] == wizard_name:
                return mage
        return None

    def _get_enemy_mage(self, wizard_name: str, observation: dict):
        for mage in observation['mages']:
            if mage['name'] != wizard_name:
                return mage
        return None
    
    def _distance(self, x1, y1, x2, y2):
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def _check_for_threats(self, wizard: 'FSMWizard', observation: dict) -> bool:
        """
        Universal threat checker. If a threat exists AND we have enough MP to evade,
        transitions to Evade and returns True.
        """
        my_mage = self._get_my_mage(wizard.name, observation)
        if not my_mage: return False
        
        # We can't evade if we don't have MP for a BLINK
        if my_mage['mp'] < 15:
            return False

        last_hp = wizard.last_known_hp.get(wizard.name, my_mage['hp'])
        if my_mage['hp'] < last_hp:
            wizard.transition_to(wizard.evade_state)
            return True

        for proj in observation['projectiles']:
            if proj['owner'] != my_mage['name']:
                w_to_p_x = proj['x'] - my_mage['x']
                w_to_p_y = proj['y'] - my_mage['y']
                dot_product = w_to_p_x * proj['vx'] + w_to_p_y * proj['vy']
                if dot_product < 0 and self._distance(my_mage['x'], my_mage['y'], proj['x'], proj['y']) < 200:
                    wizard.transition_to(wizard.evade_state)
                    return True
        return False

class IdleState(State):
    """The central state for decision making."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        if self._check_for_threats(wizard, observation):
            return wizard.current_state.execute(wizard, observation)

        my_mage = self._get_my_mage(wizard.name, observation)
        enemy_mage = self._get_enemy_mage(wizard.name, observation)
        if not my_mage or not enemy_mage: return Action('WAIT', None)

        # If MP is critically low, the ONLY option is to retreat and recover.
        if my_mage['mp'] < 15:
            wizard.transition_to(wizard.retreat_state)
            return wizard.current_state.execute(wizard, observation)

        # If we have enough MP to attack, decide whether to attack or chase.
        if my_mage['mp'] >= 30:
            dist_to_enemy = self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y'])
            if dist_to_enemy > 400:
                # Chase only if we have enough MP for the chase and a subsequent attack
                if my_mage['mp'] >= 45: 
                    dir_x = enemy_mage['x'] - my_mage['x']
                    dir_y = enemy_mage['y'] - my_mage['y']
                    dir_x /= dist_to_enemy
                    dir_y /= dist_to_enemy
                    target_x = enemy_mage['x'] - dir_x * 350
                    target_y = enemy_mage['y'] - dir_y * 350
                    return Action('BLINK', (target_x, target_y))
            else:
                wizard.transition_to(wizard.attack_state)
                return wizard.current_state.execute(wizard, observation)
        
        # If MP is between 15 and 30, it's not enough to attack, so just wait.
        return Action('WAIT', None)

class AttackState(State):
    """Attacks the enemy."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        if self._check_for_threats(wizard, observation):
            return wizard.current_state.execute(wizard, observation)

        my_mage = self._get_my_mage(wizard.name, observation)
        enemy_mage = self._get_enemy_mage(wizard.name, observation)
        
        # If we can no longer afford to attack, go back to Idle to reconsider.
        if not my_mage or not enemy_mage or my_mage['mp'] < 30 or self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y']) > 450:
            wizard.transition_to(wizard.idle_state)
            return Action('WAIT', None)
            
        return Action('FIREBALL', (enemy_mage['x'], enemy_mage['y']))

class EvadeState(State):
    """Continuously evades until no threats are present."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        # Re-check for threats. If we still have MP, keep evading.
        if self._check_for_threats(wizard, observation):
             return self._calculate_evade_action(wizard, observation)
        
        # If it's safe now, or we ran out of MP to continue evading, go to Idle.
        wizard.transition_to(wizard.idle_state)
        return Action('WAIT', None)

    def _calculate_evade_action(self, wizard, observation):
        my_mage = self._get_my_mage(wizard.name, observation)
        # The actual blink calculation remains the same.
        closest_proj = None
        min_dist = float('inf')
        for proj in observation['projectiles']:
            if proj['owner'] != my_mage['name']:
                dist = self._distance(my_mage['x'], my_mage['y'], proj['x'], proj['y'])
                if dist < min_dist:
                    min_dist = dist
                    closest_proj = proj
        if closest_proj:
            direction_x = my_mage['x'] - closest_proj['x']
            direction_y = my_mage['y'] - closest_proj['y']
            if min_dist > 0:
                direction_x /= min_dist
                direction_y /= min_dist
            evade_distance = 150
            new_x = max(50, min(observation['width'] - 50, my_mage['x'] + direction_x * evade_distance))
            new_y = max(50, min(observation['height'] - 50, my_mage['y'] + direction_y * evade_distance))
            return Action('BLINK', (new_x, new_y))
        else:
            new_x = my_mage['x'] + random.randint(-80, 80)
            new_y = my_mage['y'] + random.randint(-80, 80)
            new_x = max(50, min(observation['width'] - 50, new_x))
            new_y = max(50, min(observation['height'] - 50, new_y))
            return Action('BLINK', (new_x, new_y))


class RecoverState(State):
    """Meditates until MP is full."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        if self._check_for_threats(wizard, observation):
            return wizard.current_state.execute(wizard, observation)

        my_mage = self._get_my_mage(wizard.name, observation)
        if my_mage['mp'] == 50:
            wizard.transition_to(wizard.idle_state)
            return Action('WAIT', None)
        
        return Action('MEDITATE', None)

class RetreatState(State):
    """Moves to a safe distance to recover MP."""
    def execute(self, wizard: 'FSMWizard', observation: dict) -> Action:
        my_mage = self._get_my_mage(wizard.name, observation)
        
        # Retreat is a last resort. If we are threatened, we can't retreat.
        if self._check_for_threats(wizard, observation):
             return wizard.current_state.execute(wizard, observation)

        # If we can't even afford the blink to retreat, our ONLY hope is to meditate.
        if my_mage['mp'] < 15:
            wizard.transition_to(wizard.recover_state)
            return wizard.current_state.execute(wizard, observation)
        
        # If we have enough MP, execute the retreat blink.
        # This state is now very simple: it's just one blink, then Idle will decide the next step.
        enemy_mage = self._get_enemy_mage(wizard.name, observation)
        direction_x = my_mage['x'] - enemy_mage['x']
        direction_y = my_mage['y'] - enemy_mage['y']
        distance = self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y'])
        if distance > 0:
            direction_x /= distance
            direction_y /= distance
        
        retreat_distance = 500
        target_x = max(50, min(observation['width'] - 50, my_mage['x'] + direction_x * retreat_distance))
        target_y = max(50, min(observation['height'] - 50, my_mage['y'] + direction_y * retreat_distance))

        wizard.transition_to(wizard.idle_state) # After this one blink, go back to deciding.
        return Action('BLINK', (target_x, target_y))


class FSMWizard(BaseWizard):
    def __init__(self, name):
        super().__init__(name)
        self.idle_state = IdleState()
        self.attack_state = AttackState()
        self.evade_state = EvadeState()
        self.recover_state = RecoverState()
        self.retreat_state = RetreatState()
        
        self.current_state = self.idle_state
        self.current_state_name = "Idle"
        self.last_known_hp = {}

    def transition_to(self, new_state: State):
        self.current_state_name = new_state.__class__.__name__.replace("State", "")
        self.current_state = new_state

    def act(self, observation: dict) -> Action:
        my_mage = self.current_state._get_my_mage(self.name, observation)
        if my_mage and self.name not in self.last_known_hp:
            self.last_known_hp[self.name] = my_mage['hp']

        action = self.current_state.execute(self, observation)

        if my_mage:
             self.last_known_hp[self.name] = my_mage['hp']
        return action

    def get_debug_info(self, observation: dict) -> dict:
        return {'plan': { 'state': self.current_state_name} }