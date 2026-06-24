import random

SECTOR_SIZE = 2000

planet_types = {
    "Terran": {"credits": 5, "minerals": 2, "science": 3},
    "Desert": {"credits": 2, "minerals": 5, "science": 1},
    "Ocean": {"credits": 4, "minerals": 2, "science": 2},
    "Ice": {"credits": 1, "minerals": 4, "science": 2},
    "Volcanic": {"credits": 1, "minerals": 6, "science": 0},
    "Gas Giant": {"credits": 3, "minerals": 3, "science": 1}
}


def generate_sector(sector_x, sector_y):

    random.seed(f"{sector_x},{sector_y}")

    stars = []

    for i in range(50):

        planets = []

        for _ in range(random.randint(1, 8)):

            planet_type = random.choice(list(planet_types.keys()))
            data = planet_types[planet_type]

            planets.append({
                "type": planet_type,
                "population": 100,
                "credits": data["credits"],
                "minerals": data["minerals"],
                "science": data["science"]
            })

        stars.append({
            "x": sector_x * SECTOR_SIZE + random.randint(0, SECTOR_SIZE),
            "y": sector_y * SECTOR_SIZE + random.randint(0, SECTOR_SIZE),
            "size": random.randint(2, 5),
            "name": f"SYS-{sector_x}-{sector_y}-{i}",
            "owner": None,
            "planets": planets
        })

    return stars