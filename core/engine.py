import pygame
import math
import time
import random
from core.renderer import Renderer
from utils.logger import logger

class Mage:
    """Represents a mage in the arena."""
    def __init__(self, name, x, y, hp=100, mp=50):
        self.name = name
        self.x = x
        self.y = y
        self.hp = hp
        self.mp = mp
        self.casting_time = 0
        self.is_meditating = False

    def __repr__(self):
        return f"{self.name}(HP: {self.hp}, MP: {self.mp}, Pos: ({self.x}, {self.y}))"

class MagicArena:
    """
    Manages the game state, mage actions, and the environment for a 2D magic duel.
    """
    def __init__(self, width, height, headless=True):
        self.width = width
        self.height = height
        self.headless = headless
        self.mages = [] # Initialize mages list
        self.projectiles = []
        self.game_over = False
        self.events = [] # Event queue for things like damage numbers
        self.playable_height = int(height * 0.80)
        
        # Extended state for rendering and AI
        self.mage_states = {} # Holds AI state, casting info, etc.
        self.last_logged_states = {} # For de-duplicating state logs

        if not self.headless:
            pygame.init()
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption('Arcane Logic Arena')
            self.renderer = Renderer(self.screen, self.playable_height)

    def add_mage(self, mage):
        """Adds a mage to the arena and sets its initial position within the playable area."""
        if len(self.mages) < 2:
            # Enforce starting positions
            y_start = self.playable_height / 2
            if len(self.mages) == 0: # First mage (Merlin)
                mage.x, mage.y = 200, y_start
            else: # Second mage (Morgana)
                mage.x, mage.y = self.width - 200, y_start

            self.mages.append(mage)
            self.mage_states[mage.name] = {'state': 'Idle', 'is_casting': False, 'target': None}
        else:
            print("Arena is full. Cannot add more than 2 mages.")

    def _handle_movement(self):
        for p in self.projectiles[:]:
            p.move()
            # Remove projectiles that go off the playable area
            if not (0 < p.x < self.width and 0 < p.y < self.playable_height):
                self.projectiles.remove(p)

    def _check_collisions(self):
        for p in self.projectiles[:]:
            for m in self.mages:
                if m is not p.owner:
                    distance = math.sqrt((p.x - m.x)**2 + (p.y - m.y)**2)
                    if distance < 15:
                        damage = 10
                        m.hp -= damage
                        # Richer logging: Log damage event
                        log_msg = f"{m.name} takes {damage} damage from {p.owner.name}'s attack!"
                        logger.log(log_msg, log_type='attack')
                        self.events.append({'type': 'damage', 'pos': (m.x, m.y - 20), 'amount': damage})
                        if p in self.projectiles:
                           self.projectiles.remove(p)
                        break

    def _update_mages_status(self):
        for m in self.mages:
            if m.is_meditating:
                m.mp = min(50, m.mp + 1)
                # De-duplicated logging: Log when MP is full, but only once
                if m.mp == 50 and not self.mage_states[m.name].get('fully_charged_logged'):
                    logger.log(f"{m.name} is fully charged.", log_type='recover')
                    self.mage_states[m.name]['fully_charged_logged'] = True
            else:
                self.mage_states[m.name]['fully_charged_logged'] = False


    def _check_win_conditions(self):
        for mage in self.mages:
            if mage.hp <= 0 and not self.game_over:
                self.game_over = True
                winner = next(m for m in self.mages if m != mage)
                logger.log(f"Game Over! {winner.name} is victorious!", log_type='system')
                break
    
    def get_game_state(self, wizards={}):
        """Returns the current state of the game for AI agents and rendering."""
        mage_list_for_state = []
        for m in self.mages:
            mage_data = m.__dict__.copy()
            live_state = self.mage_states.get(m.name, {})
            mage_data.update(live_state)
            
            if m.name in wizards:
                wizard_instance = wizards[m.name]
                if hasattr(wizard_instance, 'current_state_name'):
                    current_fsm_state = wizard_instance.current_state_name
                    mage_data['state'] = current_fsm_state
                    
                    # De-duplicated logging: Log FSM state changes
                    last_state = self.last_logged_states.get(m.name)
                    if last_state != current_fsm_state:
                        logger.log(f"{m.name} is now {current_fsm_state.lower()}.", log_type='system')
                        self.last_logged_states[m.name] = current_fsm_state

                # Get debug info for rendering
                if hasattr(wizard_instance, 'get_debug_info'):
                    mage_data['debug'] = wizard_instance.get_debug_info(self.get_game_state())

            mage_list_for_state.append(mage_data)

        return {
            "mages": mage_list_for_state,
            "projectiles": [p.__dict__ for p in self.projectiles],
            "events": self.events,
            "game_over": self.game_over,
            "width": self.width,
            "height": self.height,
        }

    def _process_action(self, mage, action):
        if not action:
            return

        mage.is_meditating = False
        self.mage_states[mage.name]['is_casting'] = False
        self.mage_states[mage.name]['target'] = None
        
        command, params = action.command, action.params
        
        if command == 'FIREBALL':
            if mage.mp >= 20:
                self.cast_fireball(mage, params[0], params[1])
                self.mage_states[mage.name]['is_casting'] = True
                self.mage_states[mage.name]['target'] = params
                logger.log(f"{mage.name} casts Fireball!", log_type='attack')
        elif command == 'BLINK':
            if mage.mp >= 15:
                if not self.headless:
                    self.renderer.add_blink_effect(mage.name, (mage.x, mage.y))
                self.cast_blink(mage, params[0], params[1])
                logger.log(f"{mage.name} blinks.", log_type='system')
        elif command == 'MEDITATE':
            self.start_meditation(mage)
            # Logging is now handled in get_game_state to avoid duplicates
        elif command == 'WAIT':
            pass # Also handled in get_game_state

    def step(self, actions: dict, wizards: dict):
        self.events.clear() # Clear events at the start of the tick
        if self.game_over:
            return self.get_game_state(wizards)

        for mage in self.mages:
            if mage.name in actions:
                self._process_action(mage, actions[mage.name])

        self._handle_movement()
        self._check_collisions()
        self._update_mages_status()
        self._check_win_conditions()
        
        # Enforce stricter in-game boundaries
        for mage in self.mages:
            mage.x = max(50, min(self.width - 50, mage.x))
            mage.y = max(100, min(self.playable_height - 50, mage.y))

        return self.get_game_state(wizards)

    def cast_fireball(self, caster, target_x, target_y):
        caster.mp -= 20
        projectile = Projectile(caster.x, caster.y, target_x, target_y, owner=caster)
        self.projectiles.append(projectile)
        # Assign a unique ID for tracking trails
        projectile.id = time.time() + random.random()

    def cast_blink(self, caster, new_x, new_y):
        caster.mp -= 15
        caster.x = new_x
        caster.y = new_y

    def start_meditation(self, caster):
        caster.is_meditating = True
    
    def run_interactive(self, wizards):
        """Runs the main game loop for interactive, rendered testing."""
        if self.headless:
            print("Cannot run interactively in headless mode.")
            return

        running = True
        clock = pygame.time.Clock()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                    self.renderer.debug_mode = not self.renderer.debug_mode
                    logger.log(f"Debug mode {'ON' if self.renderer.debug_mode else 'OFF'}", log_type='system')

            if not self.game_over:
                observation = self.get_game_state(wizards)
                actions = {name: agent.act(observation) for name, agent in wizards.items()}
                current_state = self.step(actions, wizards)
            else:
                current_state = self.get_game_state(wizards)

            self.renderer.render(current_state, logger.get_messages())
            clock.tick(60)

        pygame.quit()
        
class Projectile:
    """Represents a projectile, like a fireball."""
    def __init__(self, x, y, target_x, target_y, owner, speed=5):
        self.x = x
        self.y = y
        self.owner = owner
        self.speed = speed
        
        angle = math.atan2(target_y - y, target_x - x)
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed

    def move(self):
        self.x += self.vx
        self.y += self.vy