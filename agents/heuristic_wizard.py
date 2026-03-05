import math
import random
from .base_wizard import BaseWizard, Action

class HeuristicWizard(BaseWizard):
    """
    A wizard that uses a heuristic scoring function to decide its actions.
    It evaluates all possible actions each turn and picks the one with the
    highest score.
    """
    def act(self, observation: dict) -> Action:
        my_mage = self._get_my_mage(self.name, observation)
        if not my_mage:
            return Action('WAIT', None)

        # Generate a list of potential actions
        possible_actions = self._get_possible_actions(my_mage, observation)

        # Score each action
        best_action = None
        best_score = -float('inf')

        for action in possible_actions:
            score = self._score_action(action, my_mage, observation)
            if score > best_score:
                best_score = score
                best_action = action
        
        return best_action or Action('WAIT', None)

    def _get_possible_actions(self, my_mage, observation):
        """Generates a list of all available actions."""
        actions = [Action('WAIT', None)]
        enemy_mage = self._get_enemy_mage(self.name, observation)
        
        # Fireball
        if my_mage['mp'] >= 20 and enemy_mage:
            actions.append(Action('FIREBALL', (enemy_mage['x'], enemy_mage['y'])))
            
        # Blink (to a few random safe-ish spots)
        if my_mage['mp'] >= 15:
            for _ in range(2):
                new_x = my_mage['x'] + random.uniform(-100, 100)
                new_y = my_mage['y'] + random.uniform(-100, 100)
                actions.append(Action('BLINK', (new_x, new_y)))
                
        # Meditate
        if my_mage['mp'] < 50: # Always consider meditating if not full MP
            actions.append(Action('MEDITATE', None))
            
        return actions

    def _score_action(self, action: Action, my_mage: dict, observation: dict) -> float:
        """Calculates the heuristic score for a given action."""
        score = 0
        command = action.command
        enemy_mage = self._get_enemy_mage(self.name, observation)
        dist_to_enemy = self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y']) if enemy_mage else float('inf')

        # Baseline scores for actions
        if command == 'FIREBALL':
            # Reward attacking, higher reward if enemy is close and we have MP
            score += 50
            score -= dist_to_enemy * 0.1 # Prefer closer targets
            if my_mage['mp'] < 30:
                score -= 40 # Penalize if it drains our MP too much
        
        elif command == 'BLINK':
            # High reward if HP is low
            score += (100 - my_mage['hp']) * 1.5
            # Try to blink away from the enemy
            new_x, new_y = action.params
            if enemy_mage:
                new_dist = self._distance(new_x, new_y, enemy_mage['x'], enemy_mage['y'])
                score += (new_dist - dist_to_enemy) * 0.2
        
        elif command == 'MEDITATE':
            # Reward based on how much MP is missing
            score += (50 - my_mage['mp']) * 2
            # High penalty if enemy is close
            if dist_to_enemy < 200:
                score -= 100
        
        elif command == 'WAIT':
            score += 1 # Small default score

        return score

    def get_debug_info(self, observation: dict) -> dict:
        """Calculates and returns debug information for rendering."""
        my_mage = self._get_my_mage(self.name, observation)
        if not my_mage:
            return {}

        threats = []
        for proj in observation.get('projectiles', []):
            # Consider projectiles not owned by this wizard
            if proj.get('owner') and proj.get('owner') != self.name:
                dist = self._distance(my_mage['x'], my_mage['y'], proj['x'], proj['y'])
                if dist < 250: # Only consider projectiles within a certain range
                    # Weight is higher when closer (inverse relationship)
                    weight = 1.0 - (dist / 250.0)
                    threats.append({'pos': (proj['x'], proj['y']), 'weight': weight})
        
        return {'threats': threats}

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
