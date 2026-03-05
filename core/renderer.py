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

SMOOTHING_FACTOR = 0.15
SHAKE_INTENSITY = 8
SHAKE_DURATION = 0.2

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.width = screen.get_width()
        self.height = screen.get_height()
        self.debug_mode = True

        try:
            self.font_ui = pygame.font.SysFont("Georgia", 16, bold=True)
            self.font_log = pygame.font.SysFont("Consolas", 15)
            self.font_state = pygame.font.SysFont("Georgia", 12, italic=True)
            self.font_damage = pygame.font.SysFont("Arial", 20, bold=True)
        except pygame.error:
            self.font_ui = pygame.font.Font(None, 22)
            self.font_log = pygame.font.Font(None, 21)
            self.font_state = pygame.font.Font(None, 18)
            self.font_damage = pygame.font.Font(None, 26)

        self.arcane_particles = self._create_particles(200)
        self.displayed_stats = {}
        self.vfx = {
            "blinks": [], "floating_numbers": [], "projectile_trails": {},
            "mage_effects": {}, "screen_shake_timer": 0, "last_log_count": 0,
            "log_slide_ins": deque()
        }

    def _create_particles(self, count):
        return [{'pos': [random.randint(0, self.width), random.randint(0, self.height)], 'radius': random.uniform(0.5, 1.5), 'alpha': random.randint(10, 50)} for _ in range(count)]

    def _update_state(self, game_state, log_messages):
        for mage in game_state.get("mages", []):
            name = mage['name']
            if name not in self.displayed_stats:
                self.displayed_stats[name] = {'x': mage['x'], 'y': mage['y'], 'hp': mage['hp'], 'mp': mage['mp'], 'state': mage.get('state')}
                self.vfx["mage_effects"][name] = {'last_state': mage.get('state'), 'state_change_time': 0}
            
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
        self._draw_gothic_border(render_offset)
        self._draw_projectiles_and_trails(game_state, render_offset)
        self._draw_vfx_effects(game_state, render_offset)
        self._draw_mages(game_state, render_offset)
        self._draw_ui(game_state, render_offset)
        self._draw_log(log_messages, render_offset)

        if self.debug_mode:
            self._draw_debug(game_state, render_offset)
            
        pygame.display.flip()

    def _draw_background_and_particles(self, offset):
        for y in range(self.height):
            ratio = y / self.height
            color = COLOR_BACKGROUND_DARK.lerp(COLOR_BACKGROUND_LIGHT, ratio)
            pygame.draw.line(self.screen, color, (0, y), (self.width, y))
        for p in self.arcane_particles:
            p['pos'][0] = (p['pos'][0] + 0.1) % self.width
            color = (255, 255, 255, p['alpha'])
            temp_surf = pygame.Surface((p['radius']*2, p['radius']*2), pygame.SRCALPHA)
            pygame.draw.circle(temp_surf, color, (p['radius'], p['radius']), p['radius'])
            self.screen.blit(temp_surf, (p['pos'][0]-p['radius']+offset[0], p['pos'][1]-p['radius']+offset[1]))

    def _draw_gothic_border(self, offset):
        border_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for i in range(10):
            alpha = (10 - i) * 8
            pygame.draw.rect(border_surf, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, alpha), (i*2, i*2, self.width-i*4, self.height-i*4), 2, border_radius=5)
        self.screen.blit(border_surf, offset)

    def _draw_mages(self, game_state, offset):
        for mage_data in game_state.get("mages", []):
            name = mage_data['name']
            stats = self.displayed_stats[name]
            pos = (int(stats['x']) + offset[0], int(stats['y']) + offset[1])
            color = COLOR_MAGE_A if "FSM" in name else COLOR_MAGE_B
            vfx_info = self.vfx["mage_effects"][name]

            for proj in game_state.get("projectiles", []):
                if proj.get('owner') != name:
                    dist = math.hypot(stats['x'] - proj['x'], stats['y'] - proj['y'])
                    if 20 < dist < 80:
                        self._draw_danger_zone(pos, 1 - (dist / 80))

            state_change_delta = time.time() - vfx_info['state_change_time']
            if vfx_info['last_state'] == 'Attack' and state_change_delta < 0.5:
                self._draw_rotating_ring(pos, color, 15, 2, (time.time() * (500-state_change_delta*1000))%360, 80)
                self._draw_glow(pos, color, 18, 5, 200 * (1-state_change_delta*2))
            else:
                self._draw_rotating_ring(pos, color, 12, 2, (time.time()*60)%360, 70)

            pygame.draw.circle(self.screen, color, pos, 6)
            
            state_text = mage_data.get('state', 'IDLE').upper()
            label = self.font_state.render(f"{state_text}...", True, COLOR_TEXT_GREY)
            self.screen.blit(label, (pos[0] - label.get_width() // 2, pos[1] - 38))

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

    def _draw_ui(self, game_state, offset):
        for i, mage_data in enumerate(game_state.get("mages", [])):
            self._draw_status_bars(mage_data, i == 0, offset)
            self._draw_ui_decorations(i == 0, offset)

    def _draw_ui_decorations(self, is_left, offset):
        x_base = 130 + offset[0] if is_left else self.width - 130 + offset[0]
        y_base = 40 + offset[1]
        points = [(x_base - 120, y_base + 60), (x_base, y_base - 10), (x_base + 120, y_base + 60)]
        pygame.draw.lines(self.screen, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, 50), True, points, 2)
    
    def _draw_status_bars(self, mage_data, is_left, offset):
        x_base = 30 if is_left else self.width - 230
        x_base += offset[0]
        y_base = offset[1]
        name_parts = mage_data['name'].split('_')
        formatted_name = f"{name_parts[1]} ({name_parts[0]})"
        name_label = self.font_ui.render(formatted_name, True, COLOR_TEXT_GREY)
        self.screen.blit(name_label, (x_base, 18 + y_base))
        
        stats = self.displayed_stats[mage_data['name']]
        hp_percent = stats['hp'] / 100.0
        hp_color = COLOR_HP_LOW.lerp(COLOR_HP_HIGH, hp_percent)
        self._draw_bar(x_base, 40 + y_base, hp_percent, hp_color, f"HP: {int(mage_data['hp'])}/100")
        
        mp_percent = stats['mp'] / 50.0
        self._draw_bar(x_base, 65 + y_base, mp_percent, COLOR_MP, f"MP: {int(mage_data['mp'])}/50")

    def _draw_bar(self, x, y, percent, color, label_text):
        bar_width, bar_height = 200, 15
        percent = max(0, min(1, percent))
        pygame.draw.rect(self.screen, (0,0,0,100), (x+2, y+2, bar_width, bar_height))
        pygame.draw.rect(self.screen, (50, 50, 50), (x, y, bar_width, bar_height))
        if percent > 0:
            fill_rect = pygame.Rect(x, y, int(bar_width * percent), bar_height)
            gloss_surf = pygame.Surface((fill_rect.width, fill_rect.height), pygame.SRCALPHA)
            gloss_surf.fill(color)
            pygame.draw.rect(gloss_surf, (255,255,255,50), (0,0,fill_rect.width, bar_height/2))
            self.screen.blit(gloss_surf, fill_rect.topleft)
        pygame.draw.rect(self.screen, (30, 30, 30), (x, y, bar_width, bar_height), 2)
        label = self.font_ui.render(label_text, True, COLOR_TEXT_GREY)
        self.screen.blit(label, (x + bar_width/2 - label.get_width()/2, y - 1))

    def _draw_log(self, messages, offset):
        log_height = self.height * 0.20
        log_surface = pygame.Surface((self.width, log_height), pygame.SRCALPHA)
        log_surface.fill(COLOR_LOG_BG)
        frost_surf = pygame.Surface((self.width, log_height), pygame.SRCALPHA)
        frost_surf.fill((100, 100, 100, 20))
        log_surface.blit(frost_surf, (0,0))
        color_map = {'system': COLOR_LOG_SYSTEM, 'attack': COLOR_LOG_ATTACK, 'recover': COLOR_LOG_RECOVER}
        
        for i, msg_data in enumerate(reversed(messages)):
            color = color_map.get(msg_data['type'], COLOR_LOG_SYSTEM)
            log_entry = self.font_log.render(f"> {msg_data['text']}", True, color)
            
            y_pos = log_height - (i + 1) * 22
            slide_in_offset = 0
            for slide_anim in self.vfx["log_slide_ins"]:
                if len(messages) - 1 - i == slide_anim['index']:
                    progress = (time.time() - slide_anim['start_time']) / 0.5
                    if progress < 1.0:
                        slide_in_offset = (1-progress)**2 * 20
            
            log_surface.blit(log_entry, (15, y_pos + slide_in_offset))

        self.screen.blit(log_surface, (offset[0], self.height - log_height + offset[1]))
        for i in range(50):
            ratio = i / 49
            y = self.height - log_height + math.sin(ratio * math.pi * 4) * 2
            alpha = 255 * (1 - abs(0.5-ratio)*2)
            pygame.draw.line(self.screen, (COLOR_GOLD.r, COLOR_GOLD.g, COLOR_GOLD.b, alpha), (offset[0] + self.width*ratio, y+offset[1]), (offset[0] + self.width*ratio, y+2+offset[1]))

    def _draw_vfx_effects(self, game_state, offset):
        for fn in self.vfx["floating_numbers"][:]:
            fn['y'] -= 0.5
            fn['alpha'] -= 4
            if fn['alpha'] < 0:
                self.vfx["floating_numbers"].remove(fn)
                continue
            text_surf = self.font_damage.render(fn['text'], True, (COLOR_DANGER.r, COLOR_DANGER.g, COLOR_DANGER.b, fn['alpha']))
            pos = (fn['pos'][0] + offset[0], fn['pos'][1] + offset[1] + fn['y'])
            self.screen.blit(text_surf, pos)
            
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
        self.vfx["floating_numbers"].append({'text': text, 'pos': pos, 'alpha': 255, 'y': 0})
        
    def add_blink_effect(self, name, pos):
        self.vfx["blinks"].append({'name': name, 'pos': pos, 'alpha': 255})