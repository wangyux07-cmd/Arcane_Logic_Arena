import pygame
import math
import time
import random
from collections import deque

# --- Enhanced Color Palette & VFX Constants ---
COLOR_BACKGROUND_DARK = pygame.Color("#282C34")
COLOR_BACKGROUND_LIGHT = pygame.Color("#3A404A")
COLOR_GOLD = pygame.Color("#C5A059")
COLOR_MAGE_A = pygame.Color("#8A2BE2")
COLOR_MAGE_B = pygame.Color("#DC143C")
COLOR_HP_HIGH = pygame.Color("#7CFC00")
COLOR_HP_LOW = pygame.Color("#FF0000")
COLOR_MP = pygame.Color("#00BFFF")
COLOR_LOG_BG = pygame.Color(26, 26, 27, 210)
COLOR_TEXT_GREY = pygame.Color("#EAEAEA")
COLOR_LOG_SYSTEM = pygame.Color("#B0B0B0")
COLOR_LOG_ATTACK = pygame.Color("#FF8A8A")
COLOR_LOG_RECOVER = pygame.Color("#8AFFC1")
COLOR_DANGER = pygame.Color("#FF0000")
COLOR_BACKGROUND_CENTER = pygame.Color("#1a0a2e")
COLOR_BACKGROUND_EDGE = pygame.Color("#000000")

SMOOTHING_FACTOR = 0.15
SHAKE_INTENSITY = 0
SHAKE_DURATION = 0.1

class Renderer:
    def __init__(self, screen, playable_height):
        self.screen = screen
        self.width = screen.get_width()
        self.height = screen.get_height()
        self.playable_height = playable_height
        self.debug_mode = True

        try:
            self.font_ui = pygame.font.SysFont("Georgia", 16, bold=True)
            self.font_log = pygame.font.SysFont("Consolas", 15)
            self.font_state = pygame.font.SysFont("Georgia", 10, italic=True)
            self.font_damage = pygame.font.SysFont("Arial", 20, bold=True)
        except pygame.error:
            self.font_ui = pygame.font.Font(None, 22)
            self.font_log = pygame.font.Font(None, 21)
            self.font_state = pygame.font.Font(None, 16)
            self.font_damage = pygame.font.Font(None, 26)

        self.arcane_particles = self._create_particles(200)
        
        # Pre-render the magic circle layers for performance
        self.magic_circle_radius = int(self.playable_height * 0.45)
        
        # New: Create two surfaces for the ghosting/moire effect
        self.magic_circle_light = pygame.Surface((self.magic_circle_radius * 2, self.magic_circle_radius * 2), pygame.SRCALPHA)
        self.magic_circle_dark = pygame.Surface((self.magic_circle_radius * 2, self.magic_circle_radius * 2), pygame.SRCALPHA)
        
        COLOR_MAGIC_LIGHT = pygame.Color(220, 180, 255) # Bright Lavender
        COLOR_MAGIC_DARK = pygame.Color(138, 43, 226)   # Dark Orchid

        # Draw the same complex pattern on both surfaces with different colors
        self._draw_complex_magic_circle(self.magic_circle_light, self.magic_circle_radius, COLOR_MAGIC_LIGHT)
        self._draw_complex_magic_circle(self.magic_circle_dark, self.magic_circle_radius, COLOR_MAGIC_DARK)

        self.background_surface = self._create_background_surface()
        self.displayed_stats = {}
        self.vfx = {
            "blinks": [], "floating_numbers": [], "projectile_trails": {},
            "mage_effects": {}, "screen_shake_timer": 0, "last_log_count": 0,
            "log_slide_ins": deque()
        }

    def _create_background_surface(self):
        surface = pygame.Surface((self.width, self.playable_height))
        center = (self.width // 2, self.playable_height // 2)
        max_radius = math.hypot(self.width / 2, self.playable_height / 2)

        # Draw the radial gradient only in the playable area
        for r in range(int(max_radius), 0, -5):
            ratio = r / max_radius
            color = COLOR_BACKGROUND_EDGE.lerp(COLOR_BACKGROUND_CENTER, ratio)
            pygame.draw.circle(surface, color, center, r)

        # Create a final surface of the full screen size to blit onto
        full_surface = pygame.Surface((self.width, self.height))
        full_surface.fill(COLOR_BACKGROUND_EDGE) # Fill the log area with the darkest color
        full_surface.blit(surface, (0, 0))

        return full_surface

    def _create_particles(self, count):
        return [{
            'pos': [random.randint(0, self.width), random.randint(0, self.height)],
            'radius': random.uniform(0.5, 1.5),
            'alpha': random.randint(10, 50),
            'color': (70, 70, 255) if random.random() > 0.5 else (138, 43, 226)
        } for _ in range(count)]

    def _update_state(self, game_state, log_messages):
        for mage in game_state.get("mages", []):
            name = mage['name']
            if name not in self.displayed_stats:
                self.displayed_stats[name] = {'x': mage['x'], 'y': mage['y'], 'hp': mage['hp'], 'mp': mage['mp'], 'state': mage.get('state')}
                self.vfx["mage_effects"][name] = {'last_state': mage.get('state'), 'state_change_time': 0, 'damage_flash_timer': 0}
            
            stats = self.displayed_stats[name]
            stats['x'] += (mage['x'] - stats['x']) * SMOOTHING_FACTOR
            stats['y'] += (mage['y'] - stats['y']) * SMOOTHING_FACTOR
            stats['hp'] += (mage['hp'] - stats['hp']) * SMOOTHING_FACTOR
            stats['mp'] += (mage['mp'] - stats['mp']) * SMOOTHING_FACTOR

            if mage.get('state') != self.vfx["mage_effects"][name]['last_state']:
                self.vfx["mage_effects"][name]['last_state'] = mage.get('state')
                self.vfx["mage_effects"][name]['state_change_time'] = time.time()

        for event in game_state.get("events", []):
            if event['type'] == 'damage':
                self.add_floating_number(f"-{event['amount']}", event['pos'])
                
                # Find the closest mage and trigger damage VFX
                closest_mage = min(
                    game_state.get("mages", []),
                    key=lambda m: math.hypot(m['x'] - event['pos'][0], m['y'] - event['pos'][1])
                )
                if closest_mage and math.hypot(closest_mage['x'] - event['pos'][0], closest_mage['y'] - event['pos'][1]) < 50:
                    self.vfx["mage_effects"][closest_mage['name']]['damage_flash_timer'] = 0.1
                
                self.vfx["screen_shake_timer"] = SHAKE_DURATION
        
        active_proj_ids = {p.get('id') for p in game_state.get("projectiles", [])}
        for proj in game_state.get("projectiles", []):
            proj_id = proj.get('id')
            if proj_id not in self.vfx["projectile_trails"]:
                self.vfx["projectile_trails"][proj_id] = deque(maxlen=15)
            self.vfx["projectile_trails"][proj_id].append((proj['x'], proj['y']))
        for proj_id in list(self.vfx["projectile_trails"]):
            if proj_id not in active_proj_ids:
                if len(self.vfx["projectile_trails"][proj_id]) > 0:
                     self.vfx["projectile_trails"][proj_id].popleft()
                else:
                    del self.vfx["projectile_trails"][proj_id]
        
        if len(log_messages) > self.vfx["last_log_count"]:
            self.vfx["log_slide_ins"].append({'start_time': time.time(), 'index': len(log_messages) -1})
        self.vfx["last_log_count"] = len(log_messages)
        if self.vfx["log_slide_ins"] and time.time() - self.vfx["log_slide_ins"][0]['start_time'] > 0.5:
            self.vfx["log_slide_ins"].popleft()

    def render(self, game_state: dict, log_messages: list):
        self._update_state(game_state, log_messages)
        
        render_offset = (0, 0)
        if self.vfx["screen_shake_timer"] > 0:
            self.vfx["screen_shake_timer"] -= 1/60.0
            render_offset = (random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY), random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY))

        self._draw_background_and_particles(render_offset)
        self._draw_projectiles_and_trails(game_state, render_offset)
        self._draw_vfx_effects(game_state, render_offset)
        self._draw_mages(game_state, render_offset)
        self._draw_log(log_messages, render_offset)

        if self.debug_mode:
            self._draw_debug(game_state, render_offset)
            
        pygame.display.flip()

    def _draw_background_and_particles(self, offset):
        self.screen.blit(self.background_surface, (0, 0))
        
        # --- Animated Magic Circle ---
        center_x, center_y = self.width // 2, self.playable_height // 2
        
        # Breathing effect for the circle's alpha
        breath_alpha = (math.sin(time.time() * (2 * math.pi / 3)) + 1) / 2 # 3-second cycle
        alpha = int(30 + breath_alpha * 40) # Fluctuates between 30 and 70
        
        # New: Rotate and draw the two layers with different speeds for a moire effect
        angle_light = time.time() * 10 
        angle_dark = time.time() * 12 # Slightly faster

        self._blit_rotated_surface_additive(self.screen, self.magic_circle_light, (center_x, center_y), angle_light, alpha)
        self._blit_rotated_surface_additive(self.screen, self.magic_circle_dark, (center_x, center_y), angle_dark, alpha)

        # --- Arcane Particles ---
        for p in self.arcane_particles:
            # Keep particles within the playable area
            if not (0 < p['pos'][0] < self.width and 0 < p['pos'][1] < self.playable_height):
                 p['pos'] = [random.randint(0, self.width), random.randint(0, self.playable_height)]

            dx = center_x - p['pos'][0]
            dy = center_y - p['pos'][1]
            dist = math.hypot(dx, dy)
            
            if dist < 5:  # Reset particle if it reaches the center
                p['pos'] = [random.randint(0, self.width), random.randint(0, self.playable_height)]
                if random.random() > 0.5:
                    p['pos'][0] = random.choice([0, self.width])
                else:
                    p['pos'][1] = random.choice([0, self.playable_height])
                continue

            # Move towards center
            p['pos'][0] += dx / dist * 0.2
            p['pos'][1] += dy / dist * 0.2
            
            # Use particle's color
            base_color = p['color']
            color = (
                int(base_color[0] + (255 - base_color[0]) * (p['alpha'] / 255)),
                int(base_color[1] + (255 - base_color[1]) * (p['alpha'] / 255)),
                int(base_color[2] + (255 - base_color[2]) * (p['alpha'] / 255)),
                p['alpha']
            )

            temp_surf = pygame.Surface((p['radius'] * 2, p['radius'] * 2), pygame.SRCALPHA)
            pygame.draw.circle(temp_surf, color, (p['radius'], p['radius']), p['radius'])
            self.screen.blit(temp_surf, (p['pos'][0] - p['radius'] + offset[0], p['pos'][1] - p['radius'] + offset[1]))

    def _draw_mages(self, game_state, offset):
        for mage_data in game_state.get("mages", []):
            name = mage_data['name']
            stats = self.displayed_stats[name]
            pos = (int(stats['x']) + offset[0], int(stats['y']) + offset[1])
            color = COLOR_MAGE_A if "FSM" in name else COLOR_MAGE_B
            vfx_info = self.vfx["mage_effects"][name]

            mage_pos_eff = list(pos)
            if vfx_info.get('damage_flash_timer', 0) > 0:
                vfx_info['damage_flash_timer'] -= 1/60.0
                mage_pos_eff[0] += random.randint(-2, 2)
                mage_pos_eff[1] += random.randint(-2, 2)

            # --- Name & Health Bar ---
            name_parts = mage_data['name'].split('_')
            formatted_name = f"{name_parts[1]} ({name_parts[0]})"
            name_label = self.font_ui.render(formatted_name, True, COLOR_TEXT_GREY)
            
            # --- Health Bar with Ornate Frame ---
            hp_bar_width = 70
            hp_bar_height = 9
            hp_bar_x = pos[0] - hp_bar_width // 2
            hp_bar_y = pos[1] - 70  # Positioned higher to make space for text plaque

            # Plaque for Name and State
            plaque_width = 100
            plaque_height = 40
            plaque_rect = pygame.Rect(pos[0] - plaque_width // 2, hp_bar_y + hp_bar_height + 2, plaque_width, plaque_height)
            plaque_surface = pygame.Surface((plaque_width, plaque_height), pygame.SRCALPHA)
            plaque_surface.fill((15, 15, 20, 180)) # Dark, semi-transparent background
            self.screen.blit(plaque_surface, plaque_rect.topleft)

            # Position name inside the plaque
            name_pos = (pos[0] - name_label.get_width() // 2, hp_bar_y + hp_bar_height + 5)
            self.screen.blit(name_label, name_pos)
            
            # --- Rectangular HP Bar ---
            hp_percent = max(0, stats['hp'] / 100.0)
            hp_color = COLOR_HP_LOW.lerp(COLOR_HP_HIGH, hp_percent)
            
            # Ornate frame
            frame_color_dark = (50, 45, 40)
            frame_color_light = (110, 105, 100)
            pygame.draw.rect(self.screen, frame_color_dark, (hp_bar_x - 2, hp_bar_y - 2, hp_bar_width + 4, hp_bar_height + 4))
            pygame.draw.rect(self.screen, frame_color_light, (hp_bar_x - 1, hp_bar_y - 1, hp_bar_width + 2, hp_bar_height + 2), 1)

            # Draw the background of the HP bar
            pygame.draw.rect(self.screen, (30, 10, 10), (hp_bar_x, hp_bar_y, hp_bar_width, hp_bar_height))
            # Draw the current health
            if hp_percent > 0:
                pygame.draw.rect(self.screen, hp_color, (hp_bar_x, hp_bar_y, int(hp_bar_width * hp_percent), hp_bar_height))
            
            # Add "rivets" to the frame for detail
            for dx in [-3, hp_bar_width + 1]:
                for dy in [-3, hp_bar_height + 1]:
                    pygame.draw.rect(self.screen, frame_color_light, (hp_bar_x + dx, hp_bar_y + dy, 2, 2))

            # --- Target Indicator ---
            debug_info = mage_data.get('debug', {})
            if 'plan' in debug_info and debug_info['plan'].get('type') == 'attack' and debug_info['plan'].get('target'):
                target_pos = debug_info['plan']['target']
                self._draw_target_indicator(self.screen, pos, (target_pos[0] + offset[0], target_pos[1] + offset[1]))

            # --- Rune Circle & Attack Wind-up Logic ---
            state = mage_data.get('state', 'IDLE')
            state_change_delta = time.time() - vfx_info['state_change_time']
            
            rune_radius = 25
            rune_color = COLOR_GOLD
            rotation_speed = 40
            
            if state == 'Attack':
                rune_color = pygame.Color("#FF4500")
                rotation_speed = 300
                # Attack Wind-up visual
                if state_change_delta < 0.2:
                    charge_ratio = state_change_delta / 0.2
                    rune_color = rune_color.lerp(pygame.Color("white"), 0.5 + charge_ratio * 0.5)
                    self._draw_converging_particles(mage_pos_eff, rune_radius, charge_ratio)

            elif state == 'Evade':
                rune_color = pygame.Color("#00FFFF")
                if state_change_delta < 0.4 and int(state_change_delta * 20) % 2 == 0:
                    rune_color.a = 0
                
            pulse = (math.sin(time.time() * 3) + 1) / 2
            base_alpha = 100 if state != 'Attack' else 255
            rune_color.a = int(base_alpha * pulse) if rune_color.a != 0 else 0

            rotation_angle = (time.time() * rotation_speed) % 360
            self._draw_rune_circle(self.screen, (pos[0], pos[1]), rune_color, rune_radius, rotation_angle)
            # --- End Rune Circle ---

            for proj in game_state.get("projectiles", []):
                if proj.get('owner') != name:
                    dist = math.hypot(stats['x'] - proj['x'], stats['y'] - proj['y'])
                    if 20 < dist < 80:
                        self._draw_danger_zone(pos, 1 - (dist / 80))

            if vfx_info['last_state'] == 'Attack' and state_change_delta < 0.5:
                self._draw_rotating_ring(pos, color, 15, 2, (time.time() * (500-state_change_delta*1000))%360, 80)
                self._draw_glow(pos, color, 18, 5, 200 * (1-state_change_delta*2))
            else:
                self._draw_rotating_ring(pos, color, 12, 2, (time.time()*60)%360, 70)

            # Apply white flash if being damaged
            if vfx_info.get('damage_flash_timer', 0) > 0:
                self._draw_gothic_mage(self.screen, mage_pos_eff, pygame.Color("white"))
            else:
                self._draw_gothic_mage(self.screen, mage_pos_eff, color)
            
            state_text = mage_data.get('state', 'IDLE').upper()
            label = self.font_state.render(f"{state_text}...", True, COLOR_TEXT_GREY)
            # Position state text inside the plaque, below the name
            self.screen.blit(label, (pos[0] - label.get_width() // 2, pos[1] - 25))

    def _draw_gothic_mage(self, surface, pos, color):
        # New design with clearer head, body, and weapon
        
        # Define colors
        body_color = pygame.Color(40, 40, 45)  # Darker robe
        head_color = pygame.Color(50, 50, 55)
        eye_color = pygame.Color(150, 200, 255)
        staff_color = pygame.Color(80, 50, 35) # Wood color
        
        # Robe/Body (as a polygon for a more dynamic shape)
        body_points = [
            (pos[0] - 8, pos[1] - 10),  # Top-left shoulder
            (pos[0] + 8, pos[1] - 10),  # Top-right shoulder
            (pos[0] + 15, pos[1] + 18), # Bottom-right
            (pos[0] - 15, pos[1] + 18)  # Bottom-left
        ]
        pygame.draw.polygon(surface, body_color, body_points)
        
        # Head
        head_radius = 6
        head_pos = (pos[0], pos[1] - 14)
        pygame.draw.circle(surface, head_color, head_pos, head_radius)
        
        # Eye Glow
        eye_center = head_pos
        glow_radius = head_radius * 0.5 * (1 + math.sin(time.time() * 5))
        if glow_radius > 1:
            eye_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(eye_surf, (eye_color.r, eye_color.g, eye_color.b, 120), (glow_radius, glow_radius), glow_radius)
            surface.blit(eye_surf, (eye_center[0] - glow_radius, eye_center[1] - glow_radius), special_flags=pygame.BLEND_RGBA_ADD)

        # Cloak outlines (using the mage's color)
        cloak_color = color
        pygame.draw.line(surface, cloak_color, (pos[0] - 8, pos[1] - 10), (pos[0] - 12, pos[1] + 15), 3)
        pygame.draw.line(surface, cloak_color, (pos[0] + 8, pos[1] - 10), (pos[0] + 12, pos[1] + 15), 3)

        # Staff
        staff_height = 35
        staff_width = 4
        staff_pos_x = pos[0] + 12 
        staff_start = (staff_pos_x, pos[1] - staff_height * 0.6)
        staff_end = (staff_pos_x, pos[1] + staff_height * 0.4)
        pygame.draw.line(surface, staff_color, staff_start, staff_end, staff_width)

        # Gem on top of staff
        gem_pos = (staff_start[0], staff_start[1] - 2)
        gem_radius = 5
        gem_color = color # Use the mage's theme color

        pygame.draw.circle(surface, gem_color, gem_pos, gem_radius)

        # Gem Glow effect
        pulse_alpha = 90 + 70 * math.sin(time.time() * 5)
        glow_radius = gem_radius * 2.0
        glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (gem_color.r, gem_color.g, gem_color.b, int(pulse_alpha)), (glow_radius, glow_radius), glow_radius)
        surface.blit(glow_surf, (gem_pos[0] - glow_radius, gem_pos[1] - glow_radius), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_rune_circle(self, surface, pos, color, radius, rotation_angle):
        rune_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        center = (radius, radius)
        
        # Draw the intricate rune patterns
        num_arcs = 4
        for i in range(num_arcs):
            angle = math.radians(i * (360 / num_arcs))
            rect = (0, 0, radius * 2, radius * 2)
            
            # Main arcs
            pygame.draw.arc(rune_surf, color, rect, angle, angle + math.radians(60), 2)
            
            # Inner details
            inner_radius = radius * 0.6
            inner_rect = (center[0] - inner_radius, center[1] - inner_radius, inner_radius * 2, inner_radius * 2)
            pygame.draw.arc(rune_surf, color, inner_rect, -angle, -angle + math.radians(30), 1)

        # Rotate the rune surface
        rotated_surf = pygame.transform.rotate(rune_surf, rotation_angle)
        new_rect = rotated_surf.get_rect(center=(pos[0], pos[1] + 10)) # Position under the mage
        surface.blit(rotated_surf, new_rect)

    def _draw_arc_bar(self, surface, center, radius, width, percent, color, start_angle, stop_angle):
        percent = max(0, min(1, percent))
        
        # Background arc
        bg_color = (color.r // 4, color.g // 4, color.b // 4, 100)
        pygame.draw.arc(surface, bg_color, (center[0]-radius, center[1]-radius, radius*2, radius*2), start_angle, stop_angle, width)

        # Foreground arc
        if percent > 0:
            angle_range = stop_angle - start_angle
            final_stop_angle = start_angle + angle_range * percent
            pygame.draw.arc(surface, color, (center[0]-radius, center[1]-radius, radius*2, radius*2), start_angle, final_stop_angle, width)

    def _draw_target_indicator(self, surface, pos, target_pos):
        offset_y = 28 
        indicator_size = 12

        # Angle between mage and target
        dx = target_pos[0] - pos[0]
        dy = target_pos[1] - pos[1]
        angle = math.degrees(math.atan2(-dy, dx))

        # Create a surface for the triangle, pointing right initially
        indicator_surf = pygame.Surface((indicator_size, indicator_size), pygame.SRCALPHA)
        pygame.draw.polygon(indicator_surf, (255, 60, 60, 220), 
                            [(indicator_size, indicator_size//2), (0, 0), (0, indicator_size)])
        
        # Rotate and position
        rotated_surf = pygame.transform.rotate(indicator_surf, angle - 45) # Adjust for initial shape
        blit_pos = (pos[0] - rotated_surf.get_width() // 2, 
                    pos[1] - offset_y - rotated_surf.get_height() // 2)
        surface.blit(rotated_surf, blit_pos)

    def _draw_projectiles_and_trails(self, game_state, offset):
        for proj in game_state.get("projectiles", []):
            proj_id = proj.get('id')
            pos = (int(proj['x']) + offset[0], int(proj['y']) + offset[1])
            if proj_id in self.vfx["projectile_trails"]:
                trail = self.vfx["projectile_trails"][proj_id]
                for i, p_pos in enumerate(trail):
                    alpha = (i / len(trail)) * 100
                    radius = (i / len(trail)) * 3
                    trail_pos = (p_pos[0]+offset[0], p_pos[1]+offset[1])
                    pygame.draw.circle(self.screen, (255, 165, 0, alpha), trail_pos, radius)
            self._draw_glow(pos, pygame.Color("orange"), 20, 10, 150)
            pygame.draw.circle(self.screen, pygame.Color("red"), pos, 5)

    def _draw_log(self, messages, offset):
        log_height = self.height - self.playable_height
        log_surface = pygame.Surface((self.width, log_height), pygame.SRCALPHA)
        
        # New: Add a subtle geometric pattern to the background
        log_surface.fill(COLOR_LOG_BG)
        faint_gold = (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 15)
        center_x, center_y = self.width // 2, log_height + self.magic_circle_radius # Center on magic circle
        self._draw_hexagram(log_surface, (center_x, center_y), self.magic_circle_radius * 1.5, faint_gold, 2)

        # --- Render Log Messages with Glyphs ---
        color_map = {'system': COLOR_LOG_SYSTEM, 'attack': COLOR_LOG_ATTACK, 'recover': COLOR_LOG_RECOVER}
        
        for i, msg_data in enumerate(reversed(messages)):
            y_pos = log_height - (i + 1) * 22
            if y_pos < 0: continue # Don't draw off-screen

            is_new = False
            slide_in_offset = 0
            for slide_anim in self.vfx["log_slide_ins"]:
                if len(messages) - 1 - i == slide_anim['index']:
                    is_new = True
                    progress = (time.time() - slide_anim['start_time']) / 0.5
                    if progress < 1.0:
                        slide_in_offset = (1-progress)**2 * 20
            
            # Draw glyph
            glyph_pos = (25, y_pos + 10 + slide_in_offset)
            self._draw_log_glyph(log_surface, msg_data['type'], glyph_pos, is_new)
            
            # Draw text
            color = color_map.get(msg_data['type'], COLOR_LOG_SYSTEM)
            # Make new text brighter temporarily
            if is_new:
                color = color.lerp(pygame.Color("white"), 0.6)

            log_entry = self.font_log.render(f"{msg_data['text']}", True, color)
            log_surface.blit(log_entry, (45, y_pos + slide_in_offset))

        self.screen.blit(log_surface, (offset[0], self.playable_height + offset[1]))
        
        self._draw_decorative_border(offset)

    def _draw_log_glyph(self, surface, msg_type, pos, is_new):
        glow_alpha = 200 if is_new else 100
        base_color = {
            'attack': COLOR_LOG_ATTACK,
            'recover': COLOR_LOG_RECOVER,
            'system': COLOR_LOG_SYSTEM
        }.get(msg_type, COLOR_LOG_SYSTEM)
        
        # Pulsating glow for new items
        if is_new:
            glow_alpha = 150 + 100 * abs(math.sin(time.time() * 10))

        # Draw a soft glow behind the glyph
        glow_color = (base_color.r, base_color.g, base_color.b, int(glow_alpha/4))
        pygame.draw.circle(surface, glow_color, pos, 8)
        
        # Draw the specific symbol
        if msg_type == 'attack':
            # Simple sword shape
            pygame.draw.line(surface, base_color, (pos[0], pos[1] - 5), (pos[0], pos[1] + 5), 1)
            pygame.draw.line(surface, base_color, (pos[0] - 3, pos[1] + 2), (pos[0] + 3, pos[1] + 2), 1)
        elif msg_type == 'recover':
            # Simple cross shape
            pygame.draw.line(surface, base_color, (pos[0], pos[1] - 4), (pos[0], pos[1] + 4), 1)
            pygame.draw.line(surface, base_color, (pos[0] - 4, pos[1]), (pos[0] + 4, pos[1]), 1)
        else: # system
            # Simple diamond shape
            points = [(pos[0], pos[1] - 5), (pos[0] + 4, pos[1]), (pos[0], pos[1] + 5), (pos[0] - 4, pos[1])]
            pygame.draw.polygon(surface, base_color, points, 1)

    def _draw_hexagram(self, surface, center, size, color, width):
        # Helper to draw a hexagram, used for the log background
        points1 = []
        points2 = []
        for i in range(6):
            angle_rad = math.radians(i * 60)
            points1.append((center[0] + size * math.cos(angle_rad), center[1] + size * math.sin(angle_rad)))
            angle_rad = math.radians(i * 60 + 30) # Offset for the second triangle
            points2.append((center[0] + size * 0.5 * math.cos(angle_rad), center[1] + size * 0.5 * math.sin(angle_rad)))

        pygame.draw.polygon(surface, color, [points1[0], points1[2], points1[4]], width)
        pygame.draw.polygon(surface, color, [points1[1], points1[3], points1[5]], width)

    def _draw_vfx_effects(self, game_state, offset):
        for fn in self.vfx["floating_numbers"][:]:
            fn['life'] += 1/60.0 # Assuming 60 FPS
            if fn['life'] > 1.0:
                self.vfx["floating_numbers"].remove(fn)
                continue
            
            # Pop-out and fade animation
            progress = fn['life']
            if progress < 0.5:
                # First half: pop up and scale up
                scale = 1 + progress # Grows from 1 to 1.5
                alpha = 255
            else:
                # Second half: scale down and fade out
                scale = 1.5 - (progress - 0.5) # Shrinks from 1.5 to 1
                alpha = 255 * (1 - (progress - 0.5)*2)

            font = pygame.font.SysFont("Arial", int(20 * scale), bold=True)
            
            # Render outlined text for better readability
            text_surf = font.render(fn['text'], True, (COLOR_DANGER.r, COLOR_DANGER.g, COLOR_DANGER.b, alpha))
            outline_surf = font.render(fn['text'], True, (10, 10, 10, alpha))
            
            y_offset = -20 * progress # Move upwards over lifetime
            pos = (fn['pos'][0] + offset[0], fn['pos'][1] + offset[1] + y_offset)
            
            # Blit outline first, then the main text
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                 self.screen.blit(outline_surf, (pos[0] + dx - text_surf.get_width()//2, pos[1] - text_surf.get_height()//2))
            self.screen.blit(text_surf, (pos[0] - text_surf.get_width()//2, pos[1] - text_surf.get_height()//2))

        for effect in self.vfx["blinks"][:]:
            pos, alpha, name = effect['pos'], effect['alpha'], effect['name']
            color = COLOR_MAGE_A if "FSM" in name else COLOR_MAGE_B
            if alpha <= 0:
                self.vfx["blinks"].remove(effect)
                continue
            temp_surface = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(temp_surface, (color.r, color.g, color.b, alpha), (20, 20), 10)
            self.screen.blit(temp_surface, (pos[0] - 20 + offset[0], pos[1] - 20 + offset[1]))
            effect['alpha'] -= 10

    def _draw_danger_zone(self, pos, intensity):
        alpha = int(150 * intensity * (0.5 + 0.5*math.sin(time.time()*10)))
        radius = int(30 * intensity)
        if alpha <=0 or radius <=0: return
        danger_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(danger_surf, (COLOR_DANGER.r, COLOR_DANGER.g, COLOR_DANGER.b, alpha), (radius, radius), radius)
        self.screen.blit(danger_surf, (pos[0]-radius, pos[1]-radius), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_debug(self, game_state, offset):
        for mage in game_state.get('mages', []):
            debug_info = mage.get('debug', {})
            stats = self.displayed_stats[mage['name']]
            mage_pos = (stats['x']+offset[0], stats['y']+offset[1])
            if 'threats' in debug_info:
                for threat in debug_info['threats']:
                    weight = threat.get('weight', 1.0)
                    alpha = max(50, int(weight * 255))
                    line_color = pygame.Color(255, 80, 0, alpha)
                    pygame.draw.line(self.screen, line_color, mage_pos, (threat['pos'][0]+offset[0], threat['pos'][1]+offset[1]), 1)
            if 'plan' in debug_info and debug_info['plan']:
                plan = debug_info['plan']
                target_pos = plan.get('target')
                if not target_pos: continue
                target_pos_off = (target_pos[0]+offset[0], target_pos[1]+offset[1])
                if plan['type'] == 'attack':
                    self._draw_flowing_dashed_line(pygame.Color("yellow"), mage_pos, target_pos_off)
                elif plan['type'] == 'evade':
                    self._draw_dashed_line(pygame.Color("cyan"), mage_pos, target_pos_off)
    
    def _draw_dashed_line(self, color, start_pos, end_pos, dash_length=10, gap_length=5):
        x1, y1 = start_pos
        x2, y2 = end_pos
        line_length = math.hypot(x2 - x1, y2 - y1)
        if line_length == 0: return
        dx, dy = (x2 - x1) / line_length, (y2 - y1) / line_length
        current_pos = 0
        while current_pos < line_length:
            start = (x1 + current_pos * dx, y1 + current_pos * dy)
            end_dash_pos = min(line_length, current_pos + dash_length)
            end = (x1 + end_dash_pos * dx, y1 + end_dash_pos * dy)
            pygame.draw.line(self.screen, color, start, end, 2)
            current_pos += dash_length + gap_length

    def _draw_flowing_dashed_line(self, color, start, end, dash_length=15, gap_length=10):
        offset = (time.time() * 50) % (dash_length + gap_length)
        x1, y1 = start
        x2, y2 = end
        line_length = math.hypot(x2 - x1, y2 - y1)
        if line_length == 0: return
        dx, dy = (x2 - x1) / line_length, (y2 - y1) / line_length
        current_pos = -offset
        while current_pos < line_length:
            start_dash = max(0, current_pos)
            end_dash = min(line_length, current_pos + dash_length)
            if start_dash < end_dash:
                 start_point = (x1 + start_dash * dx, y1 + start_dash * dy)
                 end_point = (x1 + end_dash * dx, y1 + end_dash * dy)
                 pygame.draw.line(self.screen, color, start_point, end_point, 1)
            current_pos += dash_length + gap_length
    
    def _draw_rotating_ring(self, pos, color, radius, width, start_angle, arc_length):
        num_arcs = 3
        for i in range(num_arcs):
            start = math.radians(start_angle + i * 120)
            end = math.radians(start_angle + i * 120 + arc_length)
            pygame.draw.arc(self.screen, color, (pos[0]-radius, pos[1]-radius, radius*2, radius*2), start, end, width)

    def _draw_glow(self, pos, color, max_radius, steps, base_alpha=100):
        for i in range(steps):
            radius = max_radius * (1 - i/steps)
            alpha = base_alpha * (1 - i/steps)
            if alpha <= 0 or radius <= 0: continue
            glow_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surface, (color.r, color.g, color.b, int(alpha)), (radius, radius), radius)
            self.screen.blit(glow_surface, (pos[0] - radius, pos[1] - radius), special_flags=pygame.BLEND_RGBA_ADD)

    def add_floating_number(self, text, pos):
        self.vfx["floating_numbers"].append({'text': text, 'pos': pos, 'life': 0.0})
        
    def add_blink_effect(self, name, pos):
        self.vfx["blinks"].append({'name': name, 'pos': pos, 'alpha': 255})
        
    def _blit_rotated_surface(self, surface, surf, pos, angle, alpha):
        # Create a new surface with the same color but different alpha
        temp_surf = surf.copy()
        temp_surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        
        rotated_surf = pygame.transform.rotate(temp_surf, angle)
        new_rect = rotated_surf.get_rect(center=pos)
        surface.blit(rotated_surf, new_rect)

    def _blit_rotated_surface_additive(self, surface, surf, pos, angle, alpha):
        # Create a new surface with the same color but different alpha
        temp_surf = surf.copy()
        temp_surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        
        rotated_surf = pygame.transform.rotate(temp_surf, angle)
        new_rect = rotated_surf.get_rect(center=pos)
        surface.blit(rotated_surf, new_rect, special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_magic_circle_layer_1(self, surface, radius):
        # Outer, more complex patterns - Rose Window inspired
        color = (255, 255, 255, 200) 
        center = (radius, radius)

    def _draw_complex_magic_circle(self, surface, radius, color):
        center = (radius, radius)

        # 1. Outermost Layer: Orderly Boundary
        # --- Clean double rings ---
        outer_r, inner_r = radius - 2, radius - 10
        pygame.draw.circle(surface, color, center, outer_r, 1)
        pygame.draw.circle(surface, color, center, inner_r, 2)

        # --- Symmetrical, clean "Runes" ---
        rune_r = (outer_r + inner_r) / 2
        for i in range(8): # 8 points, 45 degrees apart
            angle = math.radians(i * 45)
            # Draw a hollow diamond shape
            p1 = (center[0] + (rune_r) * math.cos(angle), center[1] + (rune_r) * math.sin(angle))
            p2 = (center[0] + (rune_r + 5) * math.cos(angle + math.radians(5)), center[1] + (rune_r + 5) * math.sin(angle + math.radians(5)))
            p3 = (center[0] + (rune_r) * math.cos(angle + math.radians(10)), center[1] + (rune_r) * math.sin(angle + math.radians(10)))
            p4 = (center[0] + (rune_r - 5) * math.cos(angle + math.radians(5)), center[1] + (rune_r - 5) * math.sin(angle + math.radians(5)))
            pygame.draw.polygon(surface, color, [p2,p4,p3,p1], 1)


        # 2. Middle Layer: Symmetrical Geometry
        # --- Primary Hexagram (thicker) ---
        hex_r = radius * 0.75
        hex_points1 = [
            (center[0] + hex_r * math.cos(math.radians(i * 60)), 
             center[1] + hex_r * math.sin(math.radians(i * 60)))
            for i in range(6)
        ]
        pygame.draw.polygon(surface, color, [hex_points1[0], hex_points1[2], hex_points1[4]], 2)
        pygame.draw.polygon(surface, color, [hex_points1[1], hex_points1[3], hex_points1[5]], 2)

        # --- Rotated Secondary Hexagram (thinner) to form a dodecagram ---
        hex_points2 = [
            (center[0] + hex_r * math.cos(math.radians(i * 60 + 30)), 
             center[1] + hex_r * math.sin(math.radians(i * 60 + 30)))
            for i in range(6)
        ]
        pygame.draw.polygon(surface, color, [hex_points2[0], hex_points2[2], hex_points2[4]], 1)
        pygame.draw.polygon(surface, color, [hex_points2[1], hex_points2[3], hex_points2[5]], 1)

        # --- Radial lines from inner vertices to the center ---
        inner_r_poly = radius * 0.3
        for i in range(12):
            angle = math.radians(i * 30)
            start_pos = (center[0] + inner_r_poly * math.cos(angle), center[1] + inner_r_poly * math.sin(angle))
            pygame.draw.line(surface, (color.r, color.g, color.b, 150), start_pos, center, 1)

            
        # 3. Core Layer: The Energy Nucleus
        # --- Geometric Trefoil/Trinity Knot from intersecting circles ---
        core_r = radius * 0.15
        node_r = core_r * 0.6
        for i in range(3):
            angle = math.radians(i * 120 + 90) # 3 points
            node_center = (center[0] + (core_r - node_r) * math.cos(angle),
                           center[1] + (core_r - node_r) * math.sin(angle))
            pygame.draw.circle(surface, color, node_center, node_r, 1)
        
        # --- High-bright center point ---
        bright_color = pygame.Color(min(255, color.r + 80), min(255, color.g + 80), min(255, color.b + 80))
        pygame.draw.circle(surface, bright_color, center, 3)
        
    def _draw_decorative_border(self, offset):
        line_y = self.playable_height + offset[1]
        border_height = 25 # Increased height for more detail
        
        # Create a surface for the border with per-pixel alpha
        border_surf = pygame.Surface((self.width, border_height), pygame.SRCALPHA)
        
        # --- Base Lines & Glow Effect ---
        # Main thick line
        pygame.draw.line(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 150), (0, 0), (self.width, 0), 2)
        # Thinner line below
        pygame.draw.line(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 80), (0, 3), (self.width, 3), 1)

        # Pulsating Glow
        pulse_alpha = 30 + 20 * math.sin(time.time() * 4) # Faster pulse
        glow_surf = pygame.Surface((self.width, 10), pygame.SRCALPHA)
        pygame.draw.line(glow_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, int(pulse_alpha)), (0, 2), (self.width, 2), 3)
        self.screen.blit(glow_surf, (offset[0], line_y - 4), special_flags=pygame.BLEND_RGBA_ADD)

        # --- Gothic Pattern & Details ---
        pattern_width = 100
        num_patterns = self.width // pattern_width + 1
        
        for i in range(num_patterns):
            p_x = i * pattern_width
            
            # Pointed arch shape
            arc_rect = (p_x, -border_height + 5, pattern_width, border_height * 2)
            pygame.draw.arc(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 70), arc_rect, math.pi, 2 * math.pi, 2)
            
            # Center flourish
            peak_x = p_x + pattern_width // 2
            pygame.draw.line(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 90), (peak_x, 0), (peak_x, 10), 1)
            pygame.draw.circle(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 90), (peak_x, 12), 3, 1)

        # --- Corner Designs (Fan shape) ---
        corner_radius = 40
        for x_corner in [0, self.width - corner_radius]:
            corner_rect = (x_corner, 0, corner_radius, corner_radius)
            # Draw several arcs to create a fanned effect
            for i in range(4):
                 pygame.draw.arc(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 40), 
                                (x_corner - i*4, 0, corner_radius + i*8, corner_radius), 
                                math.pi if x_corner == 0 else 0, 
                                1.5 * math.pi if x_corner == 0 else 0.5 * math.pi, 1)

        self.screen.blit(border_surf, (offset[0], line_y))

    def _draw_converging_particles(self, pos, max_radius, charge_ratio):
        num_particles = 8
        for i in range(num_particles):
            angle = math.radians(i * (360 / num_particles) + time.time() * 100)
            start_radius = max_radius * (1 - charge_ratio)
            p_pos_x = pos[0] + start_radius * math.cos(angle)
            p_pos_y = pos[1] + 10 + start_radius * math.sin(angle)
            
            # Particles get brighter as they converge
            alpha = 150 + 105 * charge_ratio
            color = (255, 255, 150, alpha)
            
            # Use a temp surface for alpha blending
            particle_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(particle_surf, color, (2, 2), 2)
            self.screen.blit(particle_surf, (p_pos_x - 2, p_pos_y - 2), special_flags=pygame.BLEND_RGBA_ADD)