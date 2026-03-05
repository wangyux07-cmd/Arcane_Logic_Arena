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

                # Failsafe: If AI logic produces a weird coordinate, default to center.
                # This helps prevent getting stuck at the absolute edge (0,0).
                if math.isnan(new_x) or math.isnan(new_y) or (new_x < 1 and new_y < 1):
                    screen_center_x = observation['width'] / 2
                    screen_center_y = observation['height'] / 2
                    new_x, new_y = screen_center_x, screen_center_y

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
        if not enemy_mage: return 0 # Can't score without an enemy

        dist_to_enemy = self._distance(my_mage['x'], my_mage['y'], enemy_mage['x'], enemy_mage['y'])
        IDEAL_DISTANCE = 350.0

        # --- Threat Assessment ---
        incoming_projectiles = [p for p in observation.get('projectiles', []) if p.get('owner') != self.name]
        nearest_threat_dist = float('inf')
        if incoming_projectiles:
            nearest_threat_dist = min(self._distance(my_mage['x'], my_mage['y'], p['x'], p['y']) for p in incoming_projectiles)

        # Baseline scores for actions
        if command == 'FIREBALL':
            # Reward attacking, but penalize if too close or too far
            score += 50
            score -= abs(dist_to_enemy - IDEAL_DISTANCE) * 0.1 # Penalty for not being at ideal distance
            if my_mage['mp'] < 30:
                score -= 40 
        
        elif command == 'BLINK':
            new_x, new_y = action.params
            
            # --- Scoring for Evasion ---
            evasion_bonus = 0
            if nearest_threat_dist < 150: # Only consider evading if a threat is close
                new_threat_dist = float('inf')
                if incoming_projectiles:
                    new_threat_dist = min(self._distance(new_x, new_y, p['x'], p['y']) for p in incoming_projectiles)
                
                # If the new position is safer, grant a large bonus
                if new_threat_dist > nearest_threat_dist:
                    evasion_bonus = 200 # High base reward for successful dodge
                    # Bonus is higher if health is low
                    evasion_bonus += (100 - my_mage['hp']) * 2
            score += evasion_bonus

            # --- Scoring for Positioning ---
            new_dist_to_enemy = self._distance(new_x, new_y, enemy_mage['x'], enemy_mage['y'])
            current_dist_error = abs(dist_to_enemy - IDEAL_DISTANCE)
            new_dist_error = abs(new_dist_to_enemy - IDEAL_DISTANCE)
            
            # Reward for improving our position (getting closer to ideal distance)
            score += (current_dist_error - new_dist_error) * 0.5
        
        elif command == 'MEDITATE':
            # Reward based on missing MP
            score += (50 - my_mage['mp']) * 1.5
            # Penalize heavily if not at a safe distance or if under threat
            if dist_to_enemy < IDEAL_DISTANCE - 50 or nearest_threat_dist < 200:
                score -= 150
        
        elif command == 'WAIT':
            # Penalize waiting if under immediate threat
            if nearest_threat_dist < 150:
                score -= 300
            else:
                score += 1

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
