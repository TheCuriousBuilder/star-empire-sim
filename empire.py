import random


class Empire:

    def __init__(self, name, color, is_ai=False):

        self.name = name
        self.color = color
        self.is_ai = is_ai

        self.systems = []

        self.credits = 1000
        self.minerals = 500
        self.science = 0

    def update_resources(self):

        for system in self.systems:

            for planet in system["planets"]:

                self.credits += planet["credits"]
                self.minerals += planet["minerals"]
                self.science += planet["science"]

    def ai_expand(self, loaded_sectors):

        if not self.systems:
            return

        unclaimed = []

        for sector in loaded_sectors.values():

            for star in sector:

                if star["owner"] is None:
                    unclaimed.append(star)

        if not unclaimed:
            return

        target = random.choice(unclaimed)

        target["owner"] = self
        self.systems.append(target)