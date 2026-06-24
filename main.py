import pygame
from galaxy import generate_sector, SECTOR_SIZE
from empire import Empire

pygame.init()

WIDTH = 1200
HEIGHT = 800

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Empire Simulator")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 30)

resource_timer = 0
ai_timer = 0

loaded_sectors = {}

player = Empire(
    "Terran Federation",
    (0, 255, 255)
)

ai_empires = [
    Empire("Orion Collective", (255, 0, 0), True),
    Empire("Nova Republic", (0, 255, 0), True),
    Empire("Zenith Dominion", (255, 255, 0), True)
]

loaded_sectors[(0, 0)] = generate_sector(0, 0)

home_stars = loaded_sectors[(0, 0)]

player_home = home_stars[0]
player_home["owner"] = player
player.systems.append(player_home)

for i, empire in enumerate(ai_empires):

    home = home_stars[i + 1]

    home["owner"] = empire
    empire.systems.append(home)

camera_x = player_home["x"]
camera_y = player_home["y"]

selected_star = None

running = True

while running:

    dt = clock.tick(60)

    resource_timer += dt
    ai_timer += dt

    current_sector_x = camera_x // SECTOR_SIZE
    current_sector_y = camera_y // SECTOR_SIZE

    for sx in range(current_sector_x - 1, current_sector_x + 2):
        for sy in range(current_sector_y - 1, current_sector_y + 2):

            key = (sx, sy)

            if key not in loaded_sectors:
                loaded_sectors[key] = generate_sector(sx, sy)

    if resource_timer >= 1000:

        player.update_resources()

        for empire in ai_empires:
            empire.update_resources()

        resource_timer = 0

    if ai_timer >= 2000:

        for empire in ai_empires:
            empire.ai_expand(loaded_sectors)

        ai_timer = 0

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN:

            mx, my = pygame.mouse.get_pos()

            for sector in loaded_sectors.values():

                for star in sector:

                    screen_x = star["x"] - camera_x + WIDTH // 2
                    screen_y = star["y"] - camera_y + HEIGHT // 2

                    dx = mx - screen_x
                    dy = my - screen_y

                    distance = (dx * dx + dy * dy) ** 0.5

                    if distance < star["size"] + 5:
                        selected_star = star

    keys = pygame.key.get_pressed()

    speed = 15

    if keys[pygame.K_a]:
        camera_x -= speed

    if keys[pygame.K_d]:
        camera_x += speed

    if keys[pygame.K_w]:
        camera_y -= speed

    if keys[pygame.K_s]:
        camera_y += speed

    if keys[pygame.K_c]:

        if selected_star:

            if selected_star["owner"] is None:

                selected_star["owner"] = player
                player.systems.append(selected_star)

    screen.fill((0, 0, 15))

    for sector in loaded_sectors.values():

        for star in sector:

            screen_x = star["x"] - camera_x + WIDTH // 2
            screen_y = star["y"] - camera_y + HEIGHT // 2

            if -10 < screen_x < WIDTH + 10 and -10 < screen_y < HEIGHT + 10:

                color = (255, 255, 220)

                if star["owner"]:
                    color = star["owner"].color

                pygame.draw.circle(
                    screen,
                    color,
                    (int(screen_x), int(screen_y)),
                    star["size"]
                )

    pygame.draw.circle(
        screen,
        (255, 0, 0),
        (WIDTH // 2, HEIGHT // 2),
        5
    )

    camera_text = font.render(
        f"Camera: {camera_x}, {camera_y}",
        True,
        (255, 255, 255)
    )

    screen.blit(camera_text, (20, 10))

    if selected_star:

        owner_name = "Unclaimed"

        if selected_star["owner"]:
            owner_name = selected_star["owner"].name

        lines = [
            selected_star["name"],
            f"Planets: {len(selected_star['planets'])}",
            f"Owner: {owner_name}",
            "Press C to colonize"
        ]

        for i, line in enumerate(lines):

            text = font.render(
                line,
                True,
                (0, 255, 0)
            )

            screen.blit(
                text,
                (20, 50 + i * 30)
            )

    empire_lines = [
        player.name,
        f"Systems: {len(player.systems)}",
        f"Credits: {player.credits}",
        f"Minerals: {player.minerals}",
        f"Science: {player.science}"
    ]

    for i, line in enumerate(empire_lines):

        text = font.render(
            line,
            True,
            (0, 200, 255)
        )

        screen.blit(
            text,
            (20, 300 + i * 30)
        )

    y = 500

    title = font.render(
        "AI Empires",
        True,
        (255, 255, 255)
    )

    screen.blit(title, (20, y))

    y += 40

    for empire in ai_empires:

        text = font.render(
            f"{empire.name}: {len(empire.systems)} systems",
            True,
            empire.color
        )

        screen.blit(text, (20, y))

        y += 30

    pygame.display.flip()

pygame.quit()

