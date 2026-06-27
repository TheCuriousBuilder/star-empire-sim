"""
main.py  –  Star Empire Simulator  (main entry point)

Controls:
  WASD / Arrow keys  – pan camera
  Q / E              – zoom out / in
  Scroll wheel       – zoom
  M                  – toggle galaxy map
  Click star         – select star
  Click fleet        – select fleet
  Right-click        – move selected fleet to selected star / attack
  Shift + Right-click– move ALL selected fleets to selected star / attack
  F                  – build fleet at selected owned star
  C                  – colonize selected unclaimed star (free if Colonization Tech)
  B                  – open Build menu for selected owned star
  T                  – open Tech tree
  R                  – open Relations panel
  ESC                – close any open panel / deselect
"""

import pygame
import sys
import math
from galaxy import generate_sector, SECTOR_SIZE, star_total_yields
from empire import Empire, TECHNOLOGIES, FLEET_COST_CREDITS, FLEET_COST_MINERALS
from planet import BUILDINGS, PLANET_TYPES

# ── INIT ──────────────────────────────────────────────────────────────────────
pygame.init()
WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Star Empire Simulator")
clock = pygame.time.Clock()
game_over = False
winner = None
# Fonts
F_XS  = pygame.font.SysFont("consolas", 16)
F_SM  = pygame.font.SysFont("consolas", 20)
F_MD  = pygame.font.SysFont("consolas", 26)
F_LG  = pygame.font.SysFont("consolas", 36)
F_XL  = pygame.font.SysFont("consolas", 52)

# Colors
BLACK   = (0,   0,  15)
DARK    = (10,  10,  25)
PANEL   = (15,  15,  35)
BORDER  = (60,  60, 120)
WHITE   = (220, 225, 255)
DIM     = (100, 110, 150)
CYAN    = (0,  220, 220)
GREEN   = (0,  210,  80)
RED     = (220,  50,  50)
YELLOW  = (255, 220,  40)
ORANGE  = (255, 140,  30)
PURPLE  = (170,  60, 255)
GOLD    = (255, 200,  50)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def draw_panel(surf, x, y, w, h, col=PANEL, border=BORDER, alpha=230):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((*col, alpha))
    surf.blit(s, (x, y))
    pygame.draw.rect(surf, border, (x, y, w, h), 1, border_radius=6)

def draw_bar(surf, x, y, w, h, val, maxv, fill, bg=(30, 30, 60)):
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=3)
    fw = int(w * max(0, min(1, val / max(maxv, 1))))
    if fw > 0:
        pygame.draw.rect(surf, fill, (x, y, fw, h), border_radius=3)
    pygame.draw.rect(surf, BORDER, (x, y, w, h), 1, border_radius=3)

def text(surf, s, font, col, x, y):
    t = font.render(str(s), True, col)
    surf.blit(t, (x, y))
    return t.get_width(), t.get_height()

def text_c(surf, s, font, col, cx, y):
    t = font.render(str(s), True, col)
    surf.blit(t, (cx - t.get_width()//2, y))
    return t.get_height()

def world_to_screen(wx, wy, cam_x, cam_y, zoom):
    sx = (wx - cam_x) * zoom + WIDTH // 2
    sy = (wy - cam_y) * zoom + HEIGHT // 2
    return int(sx), int(sy)

def screen_to_world(sx, sy, cam_x, cam_y, zoom):
    wx = (sx - WIDTH  // 2) / zoom + cam_x
    wy = (sy - HEIGHT // 2) / zoom + cam_y
    return wx, wy

def clamp(v, lo, hi): 
    return max(lo, min(hi, v))

def check_domination_victory():
    total_stars = 0
    owned_stars = 0

    for sector in loaded_sectors.values():
        for star in sector:
            total_stars += 1

            if star["owner"] is player:
                owned_stars += 1

    return owned_stars >= int(total_stars * 0.75)

# ── GAME STATE ────────────────────────────────────────────────────────────────
zoom       = 1.0
camera_x   = 0
camera_y   = 0

loaded_sectors = {}
combat_effects = []
player = Empire("Terran Federation", (0, 220, 255))
ai_empires = [
    Empire("Orion Collective", (220, 40, 40),  is_ai=True),
    Empire("Nova Republic",    (40, 210, 80),  is_ai=True),
    Empire("Zenith Dominion",  (255, 210, 40), is_ai=True),
]
all_empires = [player] + ai_empires

# Seed starting sector
GALAXY_WIDTH = 10
GALAXY_HEIGHT = 10

for sx in range(GALAXY_WIDTH):
    for sy in range(GALAXY_HEIGHT):
        loaded_sectors[(sx, sy)] = generate_sector(sx, sy)

# Assign home systems

player_home = loaded_sectors[(0, 0)][0]
player.colonize_star(player_home)

camera_x = player_home["x"]
camera_y = player_home["y"]

# AI homes in opposite corners
ai_empires[0].colonize_star(
    loaded_sectors[(9, 0)][0]
)

ai_empires[1].colonize_star(
    loaded_sectors[(0, 9)][0]
)

ai_empires[2].colonize_star(
    loaded_sectors[(9, 9)][0]
)

fleets = []          # list of fleet dicts
selected_star  = None
selected_fleets = []
combat_log     = []   # recent combat messages
notifications  = []   # (text, timer, color)

# UI state
show_galaxy_map = False
show_build_menu = False
show_tech_menu  = False
show_relations_menu = False
build_planet_idx = 0   # which planet in selected star we're building on

# Timers
resource_timer = 0
ai_timer       = 0
tick           = 0

# Stars drawn with connection lines between nearby owned stars
LANE_DIST = 600

# ── NOTIFICATION SYSTEM ───────────────────────────────────────────────────────
def notify(msg, color=CYAN):
    notifications.append([msg, 220, color])

def update_notifications():
    for n in notifications[:]:
        n[1] -= 1
        if n[1] <= 0:
            notifications.remove(n)

def draw_notifications(surf):
    y = HEIGHT - 40
    for n in reversed(notifications[-6:]):
        alpha = min(255, n[1] * 3)
        col   = tuple(int(c * alpha / 255) for c in n[2])
        tw, _ = text(surf, n[0], F_SM, col, 20, y)
        y -= 26

# ── BUILD MENU ────────────────────────────────────────────────────────────────
BUILD_SCROLL = 0

def draw_build_menu(surf):
    global build_planet_idx, BUILD_SCROLL
    if not selected_star or selected_star["owner"] is not player:
        return
    planets = selected_star["planets"]
    if not planets:
        return

    PW, PH = 460, 560
    PX, PY = WIDTH - PW - 10, 10
    draw_panel(surf, PX, PY, PW, PH)
    text_c(surf, f"BUILD  —  {selected_star['name']}", F_MD, CYAN, PX + PW//2, PY + 10)

    # Planet tabs
    tab_w = min(80, PW // len(planets))
    for i, p in enumerate(planets):
        col  = p.color
        bc   = GOLD if i == build_planet_idx else BORDER
        pygame.draw.rect(surf, col,  (PX + 8 + i*tab_w, PY+46, tab_w-4, 22), border_radius=4)
        pygame.draw.rect(surf, bc,   (PX + 8 + i*tab_w, PY+46, tab_w-4, 22), 1, border_radius=4)
        text_c(surf, p.type[:5], F_XS, WHITE, PX + 8 + i*tab_w + (tab_w-4)//2, PY+48)

    planet = planets[build_planet_idx]
    y = PY + 78
    text(surf, f"Type: {planet.type}  Pop: {planet.population:,}", F_XS, DIM, PX+8, y); y+=18
    text(surf, planet.desc, F_XS, DIM, PX+8, y); y+=18
    status = "Colonized" if planet.colonized else "Uninhabited"
    text(surf, f"Status: {status}", F_XS, GREEN if planet.colonized else RED, PX+8, y); y+=18

    if planet.buildings:
        text(surf, "Buildings: " + ", ".join(planet.buildings), F_XS, YELLOW, PX+8, y)
    y += 22

    # Yields
    yields = planet.total_yields()
    text(surf, f"Yields/tick:  Cr {yields['credits']}  Min {yields['minerals']}  Sci {yields['science']}",
         F_XS, GREEN, PX+8, y); y+=22

    pygame.draw.line(surf, BORDER, (PX+8, y), (PX+PW-8, y)); y+=8

    text(surf, "Available Buildings:", F_SM, WHITE, PX+8, y); y+=24

    # List buildings
    for bname, bdata in BUILDINGS.items():
        if y > PY + PH - 50:
            break
        ok, reason = planet.can_build(bname)
        already    = bname in planet.buildings
        col = DIM if already else (GREEN if ok else RED)

        text(surf, f"  {bname}", F_XS, col, PX+8, y)
        cost_s = f"Cr{bdata['cost_credits']} Min{bdata['cost_minerals']}"
        text(surf, cost_s, F_XS, YELLOW if ok else DIM, PX+200, y)
        if not already:
            text(surf, reason if not ok else "OK", F_XS, col, PX+340, y)
        y += 18

        # Clickable build button
        if ok and not already:
            btn = pygame.Rect(PX+8, y-18, PW-16, 18)

    text(surf, "Click a building name to build it  |  ESC close", F_XS, DIM, PX+8, PY+PH-24)

def handle_build_click(mx, my):
    """Detect clicks on building rows."""
    if not selected_star or selected_star["owner"] is not player:
        return
    planets = selected_star["planets"]
    if not planets:
        return
    PW, PH = 460, 560
    PX, PY = WIDTH - PW - 10, 10

    # Planet tab clicks
    tab_w = min(80, PW // len(planets))
    for i in range(len(planets)):
        r = pygame.Rect(PX + 8 + i*tab_w, PY+46, tab_w-4, 22)
        if r.collidepoint(mx, my):
            global build_planet_idx
            build_planet_idx = i
            return

    # Building row clicks – recompute same y positions
    planet = planets[build_planet_idx]
    y = PY + 78 + 18*3 + 22 + 22 + 8 + 24   # skip header lines
    for bname, bdata in BUILDINGS.items():
        if y > PY + PH - 50:
            break
        row = pygame.Rect(PX+8, y, PW-16, 18)
        if row.collidepoint(mx, my):
            ok, reason = planet.can_build(bname)
            already    = bname in planet.buildings
            if ok and not already:
                success, msg = planet.build(bname, player)
                notify(msg, GREEN if success else RED)
            return
        y += 18

# ── WIN ───────────────────────────────────────────────────────────────
def check_domination_victory():
    total_stars = 0
    owned_stars = 0

    for sector in loaded_sectors.values():
        for star in sector:
            total_stars += 1
            if star["owner"] is player:
                owned_stars += 1

    return owned_stars >= int(total_stars * 0.75)
# ── TECH MENU ─────────────────────────────────────────────────────────
def draw_tech_menu(surf):
    TW, TH = 680, 580
    TX = WIDTH//2 - TW//2
    TY = HEIGHT//2 - TH//2
    draw_panel(surf, TX, TY, TW, TH)
    text_c(surf, "TECHNOLOGY TREE", F_LG, CYAN, TX+TW//2, TY+10)

    # Research queue
    if player.research_queue:
        tech   = TECHNOLOGIES[player.research_queue]
        prog   = player.research_progress
        needed = tech["cost"]
        text_c(surf, f"Researching: {player.research_queue}", F_SM, YELLOW, TX+TW//2, TY+52)
        draw_bar(surf, TX+40, TY+78, TW-80, 16, prog, needed, CYAN)
        text_c(surf, f"{prog}/{needed}", F_XS, WHITE, TX+TW//2, TY+78)
    else:
        text_c(surf, "Not researching anything  —  click a tech below", F_SM, DIM, TX+TW//2, TY+52)

    pygame.draw.line(surf, BORDER, (TX+10, TY+100), (TX+TW-10, TY+100))

    # Grid by tier
    y = TY + 112
    for tier in [1, 2, 3]:
        text(surf, f"── TIER {tier} ──────────────────────", F_XS, BORDER, TX+20, y); y+=20
        row_x = TX + 20
        for tname, tdata in TECHNOLOGIES.items():
            if tdata["tier"] != tier:
                continue
            done    = tname in player.researched
            active  = player.research_queue == tname
            ok, _   = player.can_research(tname)

            if done:      col, bg = GREEN,  (10, 40, 10)
            elif active:  col, bg = YELLOW, (40, 40, 10)
            elif ok:      col, bg = WHITE,  (20, 20, 50)
            else:         col, bg = DIM,    (15, 15, 30)

            bw, bh = 300, 46
            if row_x + bw > TX+TW-10:
                row_x  = TX + 20
                y     += bh + 6

            pygame.draw.rect(surf, bg, (row_x, y, bw, bh), border_radius=5)
            pygame.draw.rect(surf, col, (row_x, y, bw, bh), 1, border_radius=5)
            text(surf, tname, F_XS, col, row_x+6, y+4)
            text(surf, tdata["desc"], F_XS, DIM, row_x+6, y+22)
            cost_s = "DONE" if done else ("ACTIVE" if active else f"Cost:{tdata['cost']} sci")
            text(surf, cost_s, F_XS, col, row_x+6, y+34)

            row_x += bw + 10

        y += 56

    text_c(surf, "Click a tech to research  |  ESC close", F_XS, DIM, TX+TW//2, TY+TH-22)

def handle_tech_click(mx, my):
    TW, TH = 680, 580
    TX = WIDTH//2 - TW//2
    TY = HEIGHT//2 - TH//2
    if not (TX <= mx <= TX+TW and TY <= my <= TY+TH):
        return False

    y = TY + 112
    for tier in [1, 2, 3]:
        y += 20
        row_x = TX + 20
        for tname, tdata in TECHNOLOGIES.items():
            if tdata["tier"] != tier:
                continue
            bw, bh = 300, 46
            if row_x + bw > TX+TW-10:
                row_x = TX + 20
                y    += bh + 6
            r = pygame.Rect(row_x, y, bw, bh)
            if r.collidepoint(mx, my):
                ok, reason = player.can_research(tname)
                if ok:
                    player.start_research(tname)
                    notify(f"Researching {tname}...", CYAN)
                else:
                    notify(reason, RED)
                return True
            row_x += bw + 10
        y += 56
    return True

# ── RELATIONS MENU ────────────────────────────────────────────────────────────
def draw_relations_menu(surf):
    DW, DH = 500, 460
    DX = WIDTH//2 - DW//2
    DY = HEIGHT//2 - DH//2
    draw_panel(surf, DX, DY, DW, DH)
    text_c(surf, "RELATIONS", F_LG, PURPLE, DX+DW//2, DY+10)
    text(surf, "Empire", F_SM, DIM, DX+20, DY+52)
    text(surf, "Status", F_SM, DIM, DX+220, DY+52)
    text(surf, "Actions", F_SM, DIM, DX+320, DY+52)
    pygame.draw.line(surf, BORDER, (DX+10, DY+74), (DX+DW-10, DY+74))

    y = DY + 82
    for emp in ai_empires:
        rel = player.get_relation(emp.name)
        rc  = {
            "Neutral": DIM, "Allied": GREEN, "War": RED,
            "Trade Pact": YELLOW, "Peace Treaty": CYAN
        }.get(rel, WHITE)

        # empire dot
        pygame.draw.circle(surf, emp.color, (DX+14, y+10), 8)
        text(surf, emp.name, F_SM, WHITE, DX+28, y)
        text(surf, rel, F_XS, rc, DX+220, y+2)
        text(surf, f"{len(emp.systems)} sys", F_XS, DIM, DX+220, y+18)

        # Action buttons
        btns = []
        if rel != "War":
            btns.append(("WAR", RED))
        if rel == "War":
            btns.append(("PEACE", GREEN))
        if rel not in ("Allied", "Trade Pact"):
            btns.append(("TRADE", YELLOW))
        if rel not in ("Allied",):
            btns.append(("ALLY", CYAN))

        bx = DX + 330
        for label, col in btns:
            bw = F_XS.size(label)[0] + 14
            pygame.draw.rect(surf, (30,30,60), (bx, y, bw, 22), border_radius=4)
            pygame.draw.rect(surf, col,       (bx, y, bw, 22), 1, border_radius=4)
            text(surf, label, F_XS, col, bx+7, y+4)
            bx += bw + 6

        y += 60

    text_c(surf, "ESC to close", F_XS, DIM, DX+DW//2, DY+DH-22)

def handle_relations_click(mx, my):
    DW, DH = 500, 460
    DX = WIDTH//2 - DW//2
    DY = HEIGHT//2 - DH//2
    if not (DX <= mx <= DX+DW and DY <= my <= DY+DH):
        return False

    y = DY + 82
    for emp in ai_empires:
        rel = player.get_relation(emp.name)
        btns = []
        if rel != "War":    btns.append(("WAR", RED))
        if rel == "War":    btns.append(("PEACE", GREEN))
        if rel not in ("Allied","Trade Pact"): btns.append(("TRADE", YELLOW))
        if rel not in ("Allied",):             btns.append(("ALLY",  CYAN))

        bx = DX + 330
        for label, col in btns:
            bw = F_XS.size(label)[0] + 14
            r  = pygame.Rect(bx, y, bw, 22)
            if r.collidepoint(mx, my):
                if label == "WAR":
                    player.declare_war(emp)
                    notify(f"You declared war on {emp.name}!", RED)
                elif label == "PEACE":
                    player.make_peace(emp)
                    notify(f"Peace with {emp.name}.", GREEN)
                elif label == "TRADE":
                    player.propose_trade(emp)
                    notify(f"Trade pact with {emp.name}.", YELLOW)
                elif label == "ALLY":
                    player.propose_alliance(emp)
                    notify(f"Alliance with {emp.name}!", CYAN)
                return True
            bx += bw + 6
        y += 60
    return True

# ── STAR INFO PANEL ───────────────────────────────────────────────────────────
def draw_star_info(surf):
    if not selected_star:
        return
    star = selected_star
    PW, PH = 310, 420
    PX, PY = 10, 10
    draw_panel(surf, PX, PY, PW, PH)

    owner_name = star["owner"].name if star["owner"] else "Unclaimed"
    owner_col  = star["owner"].color if star["owner"] else DIM

    y = PY + 8
    text_c(surf, star["name"], F_MD, WHITE, PX+PW//2, y);   y+=30
    text(surf, f"Owner: {owner_name}", F_XS, owner_col, PX+8, y); y+=18
    text(surf, f"Planets: {len(star['planets'])}", F_XS, DIM, PX+8, y); y+=18

    # Yields
    yields = star_total_yields(star)
    text(surf, f"Total Yields/tick:", F_XS, DIM, PX+8, y); y+=16
    text(surf, f"  Credits:  {yields['credits']}", F_XS, GOLD, PX+8, y); y+=16
    text(surf, f"  Minerals: {yields['minerals']}", F_XS, ORANGE, PX+8, y); y+=16
    text(surf, f"  Science:  {yields['science']}", F_XS, CYAN, PX+8, y); y+=20

    pygame.draw.line(surf, BORDER, (PX+8, y), (PX+PW-8, y)); y+=8

    # Planets list
    text(surf, "Planets:", F_SM, WHITE, PX+8, y); y+=20
    for i, p in enumerate(star["planets"][:8]):
        col = p.color
        status = "✓" if p.colonized else "·"
        pygame.draw.circle(surf, col, (PX+18, y+8), 7)
        text(surf, f"{status} {p.type}", F_XS, col, PX+30, y)
        if p.colonized and p.buildings:
            bstr = ",".join(b[:4] for b in p.buildings[:3])
            text(surf, bstr, F_XS, DIM, PX+150, y)
        y += 18

    pygame.draw.line(surf, BORDER, (PX+8, y), (PX+PW-8, y)); y+=8

    # Fleets here
    here = sum(1 for f in fleets if f["x"] == star["x"] and f["y"] == star["y"])
    if here:
        text(surf, f"Fleets present: {here}", F_XS, PURPLE, PX+8, y); y+=18

    # Actions
    y = PY + PH - 80
    if star["owner"] is None:
        text(surf, "[C] Colonize", F_XS, GREEN, PX+8, y); y+=18
    elif star["owner"] is player:
        text(surf, "[F] Build Fleet (100Cr 80Min)", F_XS, YELLOW, PX+8, y); y+=18
        text(surf, "[B] Build Menu", F_XS, CYAN, PX+8, y); y+=18
    else:
        rel = player.get_relation(star["owner"].name)
        text(surf, f"Relation: {rel}", F_XS,
             RED if rel=="War" else GREEN, PX+8, y); y+=18
        if rel == "War":
            text(surf, "[Right-click fleet] Attack!", F_XS, RED, PX+8, y); y+=18

# ── EMPIRE PANEL ──────────────────────────────────────────────────────────────
def draw_empire_panel(surf):
    PW, PH = 280, 220
    PX = WIDTH - PW - 10
    PY = HEIGHT - PH - 10
    draw_panel(surf, PX, PY, PW, PH)

    y = PY + 8
    text(surf, player.name, F_SM, CYAN, PX+8, y); y+=26

    draw_bar(surf, PX+8, y, PW-16, 12, player.credits,  9999, GOLD)
    text(surf, f"Credits:  {player.credits}", F_XS, GOLD, PX+8, y-1); y+=18

    draw_bar(surf, PX+8, y, PW-16, 12, player.minerals, 9999, ORANGE)
    text(surf, f"Minerals: {player.minerals}", F_XS, ORANGE, PX+8, y-1); y+=18

    draw_bar(surf, PX+8, y, PW-16, 12, player.science,  9999, CYAN)
    text(surf, f"Science:  {player.science}", F_XS, CYAN, PX+8, y-1); y+=18

    text(surf, f"Systems:  {len(player.systems)}", F_XS, WHITE, PX+8, y); y+=18
    text(surf, f"Fleets:   {sum(1 for f in fleets if f['owner'] is player)}", F_XS, WHITE, PX+8, y); y+=18

    if player.research_queue:
        prog = player.research_progress
        cost = TECHNOLOGIES[player.research_queue]["cost"]
        text(surf, f"Research: {player.research_queue[:20]}", F_XS, YELLOW, PX+8, y); y+=16
        draw_bar(surf, PX+8, y, PW-16, 8, prog, cost, YELLOW)
    else:
        text(surf, "[T] Open Tech Tree", F_XS, DIM, PX+8, y)

# ── AI PANEL ──────────────────────────────────────────────────────────────────
def draw_ai_panel(surf):
    PW, PH = 260, 30 + len(ai_empires) * 38
    PX = WIDTH - PW - 10
    PY = 10
    draw_panel(surf, PX, PY, PW, PH)
    text_c(surf, "EMPIRES", F_SM, WHITE, PX+PW//2, PY+6)

    y = PY + 32
    for emp in ai_empires:
        pygame.draw.circle(surf, emp.color, (PX+14, y+10), 8)
        text(surf, emp.name[:18], F_XS, emp.color, PX+28, y)
        text(surf, f"{len(emp.systems)} sys", F_XS, DIM, PX+28, y+16)
        rel = player.get_relation(emp.name)
        rc  = {"War": RED, "Allied": GREEN, "Trade Pact": YELLOW}.get(rel, DIM)
        text(surf, rel, F_XS, rc, PX+160, y+8)
        y += 38

# ── MINIMAP ───────────────────────────────────────────────────────────────────
MM_X, MM_Y, MM_S = WIDTH - 270, HEIGHT - 210, 200

def draw_minimap(surf):
    draw_panel(surf, MM_X, MM_Y, MM_S, MM_S, col=(5, 5, 20))
    pygame.draw.rect(surf, PURPLE, (MM_X, MM_Y, MM_S, MM_S), 1)
    text(surf, "MAP (M)", F_XS, PURPLE, MM_X+4, MM_Y-18)

    for sector in loaded_sectors.values():
        for star in sector:
            dx = star["x"] - camera_x
            dy = star["y"] - camera_y
            mx = MM_X + MM_S//2 + int(dx / 45)
            my = MM_Y + MM_S//2 + int(dy / 45)
            if MM_X <= mx <= MM_X+MM_S and MM_Y <= my <= MM_Y+MM_S:
                col = star["owner"].color if star["owner"] else (60, 60, 80)
                pygame.draw.circle(surf, col, (mx, my), 2)

    # Player position dot
    pygame.draw.circle(surf, WHITE, (MM_X+MM_S//2, MM_Y+MM_S//2), 4)

    # Fleet dots
    for f in fleets:
        dx = f["x"] - camera_x
        dy = f["y"] - camera_y
        fx = MM_X + MM_S//2 + int(dx / 45)
        fy = MM_Y + MM_S//2 + int(dy / 45)
        if MM_X <= fx <= MM_X+MM_S and MM_Y <= fy <= MM_Y+MM_S:
            pygame.draw.circle(surf, f["owner"].color, (fx, fy), 3)

def draw_galaxy_map(surf):
    surf.fill((5, 5, 15))
    text_c(surf, "GALAXY MAP  (M to close)", F_LG, PURPLE, WIDTH//2, 16)
    for sector in loaded_sectors.values():
        for star in sector:
            dx = star["x"] - camera_x
            dy = star["y"] - camera_y
            mx = WIDTH//2 + int(dx / 20)
            my = HEIGHT//2 + int(dy / 20)
            if 0 <= mx < WIDTH and 0 <= my < HEIGHT:
                col = star["owner"].color if star["owner"] else (50, 50, 70)
                r   = 3 if star["owner"] else 1
                pygame.draw.circle(surf, col, (mx, my), r)
    pygame.draw.circle(surf, WHITE, (WIDTH//2, HEIGHT//2), 6)

    # Legend
    y = HEIGHT - 120
    text(surf, "Legend:", F_SM, WHITE, 20, y); y+=24
    for emp in all_empires:
        pygame.draw.circle(surf, emp.color, (30, y+8), 6)
        text(surf, emp.name, F_XS, emp.color, 44, y); y+=22

# ── DRAW WORLD ────────────────────────────────────────────────────────────────
def draw_world(surf):
    # Trade lane lines between nearby owned stars of same empire
    if zoom > 0.4:
        all_stars = [s for sec in loaded_sectors.values() for s in sec if s["owner"]]
        for i, s1 in enumerate(all_stars):
            for s2 in all_stars[i+1:]:
                if s1["owner"] is not s2["owner"]:
                    continue
                dx = s2["x"] - s1["x"]; dy = s2["y"] - s1["y"]
                if dx*dx + dy*dy > LANE_DIST**2:
                    continue
                x1, y1 = world_to_screen(s1["x"], s1["y"], camera_x, camera_y, zoom)
                x2, y2 = world_to_screen(s2["x"], s2["y"], camera_x, camera_y, zoom)
                col = tuple(c // 4 for c in s1["owner"].color)
                pygame.draw.line(surf, col, (x1,y1), (x2,y2), 1)

    # Stars
    for sector in loaded_sectors.values():
        for star in sector:
            sx, sy = world_to_screen(star["x"], star["y"], camera_x, camera_y, zoom)
            if -60 < sx < WIDTH+60 and -60 < sy < HEIGHT+60:
                col  = star.get("color", (255, 255, 200))
                r    = max(1, int(star["size"] * zoom))

                # Nebula glow
                if star.get("in_nebula") and zoom > 0.5:
                    ng = pygame.Surface((r*6, r*6), pygame.SRCALPHA)
                    pygame.draw.circle(ng, (*col, 30), (r*3, r*3), r*3)
                    surf.blit(ng, (sx - r*3, sy - r*3))

                # Owner tint ring
                if star["owner"]:
                    pygame.draw.circle(surf, star["owner"].color, (sx, sy), r+4, 1)

                pygame.draw.circle(surf, col, (sx, sy), r)

                # Selection ring
                if star is selected_star:
                    pulse = int(abs(math.sin(tick * 0.06)) * 3)
                    pygame.draw.circle(surf, WHITE, (sx, sy), r + 8 + pulse, 1)

                # Name label at close zoom
                if zoom > 1.5:
                    t = F_XS.render(star["name"], True, DIM)
                    surf.blit(t, (sx - t.get_width()//2, sy + r + 4))

    # Fleets
    for fleet in fleets:
        sx, sy = world_to_screen(fleet["x"], fleet["y"], camera_x, camera_y, zoom)
        if -60 < sx < WIDTH+60 and -60 < sy < HEIGHT+60:
            col = fleet["owner"].color
            r   = max(8, int(12*zoom))
            pygame.draw.circle(surf, col, (sx, sy), r, 2)
            pygame.draw.circle(surf, col, (sx, sy), r+5, 1)

            # Movement line to target
            tx, ty = world_to_screen(fleet["target_x"], fleet["target_y"],
                                     camera_x, camera_y, zoom)
            pygame.draw.line(surf, tuple(c//3 for c in col), (sx,sy), (tx,ty), 1)

            if fleet in selected_fleets:
                pygame.draw.circle(surf, WHITE, (sx, sy), r+9, 1)

            # HP bar above fleet
            if fleet.get("hp") is not None:
                draw_bar(surf, sx-20, sy-r-10, 40, 5,
                         fleet["hp"], fleet.get("max_hp", fleet["hp"]), GREEN)
    # Combat explosions
    for effect in combat_effects:
        sx, sy = world_to_screen(
            effect["x"],
            effect["y"],
            camera_x,
            camera_y,
            zoom
        )

        radius = int(effect["radius"] * zoom)

        if radius > 0:
            pygame.draw.circle(
                surf,
                effect["color"],
                (sx, sy),
                radius,
                2
            )
# ── CONTROLS OVERLAY ─────────────────────────────────────────────────────────
def draw_controls(surf):
    hints = [
        "WASD: pan   Q/E: zoom   M: map",
        "Click: select   F: fleet   C: colonize",
        "B: build   T: tech   R: relations   ESC: close",
        "RMB: move fleet / attack",
    ]
    y = HEIGHT - 22 - len(notifications)*26 - len(hints)*17 - 10
    for h in hints:
        text(surf, h, F_XS, (50, 55, 90), 20, y); y+=17

# ── MAIN LOOP ─────────────────────────────────────────────────────────────────
running = True

while running:
    dt  = clock.tick(60)
    tick += 1
    resource_timer += dt
    ai_timer       += dt
    # Resource tick (every second)
    if resource_timer >= 1000:
        player.update_resources()
        for emp in ai_empires:
            emp.update_resources()
        resource_timer = 0

    # AI tick (every 2 seconds)
    if ai_timer >= 2000:
        for emp in ai_empires:
            emp.ai_turn(loaded_sectors, all_empires, fleets)
        ai_timer = 0

    update_notifications()

    # ── EVENTS ────────────────────────────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            k = event.key

            if k == pygame.K_ESCAPE:

                if game_over:
                    running = False

                elif show_build_menu:
                    show_build_menu = False

                elif show_tech_menu:
                    show_tech_menu = False

                elif show_relations_menu:
                    show_relations_menu = False

                elif show_galaxy_map:
                    show_galaxy_map = False

                else:
                    selected_star = None
                    selected_fleets.clear()

            elif k == pygame.K_m:
                show_galaxy_map = not show_galaxy_map
                show_build_menu = show_tech_menu = show_relations_menu = False

            elif k == pygame.K_b:
                if selected_star and selected_star["owner"] is player:
                    show_build_menu = not show_build_menu
                    show_tech_menu = show_relations_menu = False
                else:
                    notify("Select one of your systems first.", RED)

            elif k == pygame.K_t:
                show_tech_menu  = not show_tech_menu
                show_build_menu = show_relations_menu = False

            elif k == pygame.K_r:
                show_relations_menu = not show_relations_menu
                show_build_menu = show_tech_menu = False

            elif k == pygame.K_f:
                if selected_star and selected_star["owner"] is player:
                    if player.can_build_fleet():
                        player.spend_fleet_cost()
                        fleets.append({
                            "x": selected_star["x"],
                            "y": selected_star["y"],
                            "target_x": selected_star["x"],
                            "target_y": selected_star["y"],
                            "target_star": None,
                            "owner": player,
                            "hp": player.fleet_hp(),
                            "max_hp": player.fleet_hp(),
                            "damage": player.fleet_damage(),
                            "speed": player.fleet_speed(),
                            "combat_target": None,
                        })
                        notify("Fleet built!", GREEN)
                    else:
                        notify(f"Need {FLEET_COST_CREDITS}Cr + {FLEET_COST_MINERALS}Min to build fleet.", RED)
                else:
                    notify("Select one of your systems first.", RED)

            elif k == pygame.K_c:
                if selected_star:
                    if selected_star["owner"] is None:
                        player.colonize_star(selected_star)
                        if check_domination_victory():
                            game_over = True
                            winner = player
                        notify(f"Colonized {selected_star['name']}!", GREEN)
                        # Remove any enemy fleets parked at newly colonized star
                        for ef in fleets[:]:
                            if (ef["owner"] is not player and
                                    abs(ef["x"] - selected_star["x"]) < 5 and
                                    abs(ef["y"] - selected_star["y"]) < 5):
                                fleets.remove(ef)
                    else:
                        notify("Already owned.", RED)
                else:
                    notify("Select a star first.", RED)

        if event.type == pygame.MOUSEWHEEL:
            zoom = clamp(zoom + event.y * 0.1, 0.08, 6.0)

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos

            # Panel clicks first
            if show_build_menu and event.button == 1:
                handle_build_click(mx, my)
                continue
            if show_tech_menu and event.button == 1:
                if handle_tech_click(mx, my):
                    continue
            if show_relations_menu and event.button == 1:
                if handle_relations_click(mx, my):
                    continue

            if event.button == 1:
                # Deselect
                selected_star  = None
                selected_fleet = None

                # Select star
                for sector in loaded_sectors.values():
                    for star in sector:
                        sx, sy = world_to_screen(star["x"], star["y"],
                                                  camera_x, camera_y, zoom)
                        dx = mx - sx; dy = my - sy
                        if (dx*dx + dy*dy)**0.5 < max(6, star["size"]*zoom + 6):
                            selected_star = star
                            break

                # Select fleet
                mods = pygame.key.get_mods()

                for fleet in fleets:
                    fx, fy = world_to_screen(
                        fleet["x"],
                        fleet["y"],
                        camera_x,
                        camera_y,
                        zoom
                    )

                    if (mx-fx)**2 + (my-fy)**2 < 20**2:

                        if mods & pygame.KMOD_SHIFT:
                            if fleet not in selected_fleets:
                                selected_fleets.append(fleet)
                        else:
                            selected_fleets = [fleet]

                        break

            elif event.button == 3:
                # Right-click: move fleet or attack
                if selected_fleets:
                    # Find clicked star
                    target_star = None

                    for sector in loaded_sectors.values():
                        for star in sector:
                            sx, sy = world_to_screen(
                                star["x"],
                                star["y"],
                                camera_x,
                                camera_y,
                                zoom
                            )

                            if (mx-sx)**2 + (my-sy)**2 < max(10, star["size"]*zoom+6)**2:
                                target_star = star
                                break

                    if target_star is None:
                        continue

                    mods = pygame.key.get_mods()

                    fleet_group = selected_fleets

                    # Shift + right click = every player fleet
                    if mods & pygame.KMOD_SHIFT:
                        fleet_group = [f for f in fleets if f["owner"] is player]

                    for fleet in fleet_group:

                        fleet["target_x"] = target_star["x"]
                        fleet["target_y"] = target_star["y"]
                        fleet["target_star"] = target_star

                        if (
                            target_star["owner"]
                            and target_star["owner"] is not player
                            and player.get_relation(target_star["owner"].name) == "War"
                        ):
                            fleet["combat_target"] = target_star["owner"]
                        else:
                            fleet["combat_target"] = None
                        # Check for attack
                        if (
                            target_star["owner"]
                            and target_star["owner"] is not player
                            and player.get_relation(target_star["owner"].name) == "War"
                        ):
                            if mods & pygame.KMOD_SHIFT:
                                notify(f"ALL fleets moving to attack {target_star['name']}!", RED)
                            else:
                                notify(f"{len(fleet_group)} fleet(s) moving to attack {target_star['name']}!", RED)
                        else:
                            if mods & pygame.KMOD_SHIFT:
                                notify(f"ALL fleets ordered to {target_star['name']}!", CYAN)
                            else:
                                notify(f"{len(fleet_group)} fleet(s) ordered to {target_star['name']}", CYAN)
    # ── CAMERA ────────────────────────────────────────────────────────────────
    keys  = pygame.key.get_pressed()
    speed = int(15 / zoom)
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:  camera_x -= speed
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]: camera_x += speed
    if keys[pygame.K_w] or keys[pygame.K_UP]:    camera_y -= speed
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:  camera_y += speed
    if keys[pygame.K_q]: zoom = clamp(zoom - 0.02, 0.08, 6.0)
    if keys[pygame.K_e]: zoom = clamp(zoom + 0.02, 0.08, 6.0)
    # Keep camera inside galaxy
    GALAXY_PIXEL_WIDTH = GALAXY_WIDTH * SECTOR_SIZE
    GALAXY_PIXEL_HEIGHT = GALAXY_HEIGHT * SECTOR_SIZE

    camera_x = clamp(
        camera_x,
        0,
        GALAXY_PIXEL_WIDTH
    )

    camera_y = clamp(
        camera_y,
        0,
        GALAXY_PIXEL_HEIGHT
    )
    # ── FLEET MOVEMENT & COMBAT ───────────────────────────────────────────────
    for fleet in fleets[:]:
        dx = fleet["target_x"] - fleet["x"]
        dy = fleet["target_y"] - fleet["y"]
        dist = (dx*dx + dy*dy) ** 0.5

        spd = fleet.get("speed", BASE_FLEET_SPEED := 2.0)

        if dist > 2:
            fleet["x"] += dx / dist * spd
            fleet["y"] += dy / dist * spd
        else:
            fleet["x"] = fleet["target_x"]
            fleet["y"] = fleet["target_y"]

            # Arrived -- check combat
            ts = fleet.get("target_star")
            ct = fleet.get("combat_target")
            if ts and ct and ts["owner"] is ct:
                # Fight!
                victory, log = fleet["owner"].resolve_combat(fleet, ct, ts)
                combat_effects.append({
                    "x": ts["x"],
                    "y": ts["y"],
                    "radius": 10,
                    "timer": 45,
                    "color": RED
                })
                for line in log:
                    notify(line, GREEN if victory else RED)
                    combat_log.append(line)
                
                if not victory:
                    fleets.remove(fleet)
                else:
                    fleet["combat_target"] = None
                    fleet["target_star"]   = None

                    if check_domination_victory():
                        game_over = True
                        winner = player
                    # Destroy enemy fleets parked at the captured star
                    for ef in fleets[:]:
                        if (ef is not fleet and
                                ef["owner"] is ct and
                                abs(ef["x"] - ts["x"]) < 5 and
                                abs(ef["y"] - ts["y"]) < 5):
                            fleets.remove(ef)
                    # Cancel orders of all enemy fleets en-route to this star
                    for ef in fleets:
                        if ef["owner"] is ct and ef.get("target_star") is ts:
                            ef["combat_target"] = None
                            ef["target_star"]   = None
                            ef["target_x"]      = ef["x"]
                            ef["target_y"]      = ef["y"]
    # ── ARROWS/ANIMATIONS ──────────────────────────────────────────────────────────────────
    def draw_enemy_arrows(surf):
        center_x = WIDTH // 2
        center_y = HEIGHT // 2

        for emp in ai_empires:
            if not emp.systems:
                continue

            # Average position of empire
            avg_x = sum(star["x"] for star in emp.systems) / len(emp.systems)
            avg_y = sum(star["y"] for star in emp.systems) / len(emp.systems)

            dx = avg_x - camera_x
            dy = avg_y - camera_y

            dist = math.hypot(dx, dy)

            # Don't show arrow if empire is already on screen
            if dist < 1200:
                continue

            angle = math.atan2(dy, dx)

            radius = min(WIDTH, HEIGHT) // 2 - 50

            ax = center_x + math.cos(angle) * radius
            ay = center_y + math.sin(angle) * radius

            size = 18

            tip = (
                ax + math.cos(angle) * size,
                ay + math.sin(angle) * size
            )

            left = (
                ax + math.cos(angle + 2.5) * size,
                ay + math.sin(angle + 2.5) * size
            )

            right = (
                ax + math.cos(angle - 2.5) * size,
                ay + math.sin(angle - 2.5) * size
            )

            pygame.draw.polygon(
                surf,
                emp.color,
                [tip, left, right]
            )

            text(
                surf,
                emp.name,
                F_XS,
                emp.color,
                int(ax + 20),
                int(ay - 10)
            )
    for effect in combat_effects[:]:
        effect["timer"] -= 1
        effect["radius"] += 2

        if effect["timer"] <= 0:
            combat_effects.remove(effect)
    # ── DRAW ──────────────────────────────────────────────────────────────────
    screen.fill(BLACK)

    if show_galaxy_map:
        draw_galaxy_map(screen)
    else:
        draw_world(screen)
        draw_enemy_arrows(screen)
        draw_minimap(screen)
        draw_star_info(screen)
        draw_empire_panel(screen)
        draw_ai_panel(screen)
        draw_controls(screen)

        if show_build_menu: draw_build_menu(screen)
        if show_tech_menu:  draw_tech_menu(screen)
        if show_relations_menu: draw_relations_menu(screen)

    draw_notifications(screen)

    # Tiny tick counter (top center)
    text_c(screen, f"Year {tick // 60 + 1}  |  Tick {tick}", F_XS, (40,44,70), WIDTH//2, 4)
    if game_over:
        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(220)
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0))

        text_c(
            screen,
            f"{winner.name} WINS!",
            F_XL,
            GOLD,
            WIDTH // 2,
            HEIGHT // 2 - 40
        )

        text_c(
            screen,
            "Press ESC to quit",
            F_MD,
            WHITE,
            WIDTH // 2,
            HEIGHT // 2 + 30
        )
    pygame.display.flip()

pygame.quit()
sys.exit()