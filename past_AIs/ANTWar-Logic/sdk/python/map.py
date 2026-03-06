from ant import Ant
from aco import d
from protocol import Pos


class Tower:
    def __init__(self) -> None:
        self.id = 0
        self.x = 0
        self.y = 0
        self.level = 0
        self.player = 0
        self.cd = 0
        self.power = 0
        # self.cost = 0

    def get_cd(self):
        if self.level == 0 or self.level == 1 or self.level == 11 or self.level == 12 or self.level == 23:
            return 2
        elif self.level == 2 or self.level == 22 or self.level == 21:
            return 1
        elif self.level == 13 or self.level == 3 or self.level == 31:
            return 4
        elif self.level == 32:
            return 3
        elif self.level == 33:
            return 6

    def get_range(self):
        if self.level == 0 or self.level == 1 or self.level == 12 or self.level == 11 or self.level == 32:
            return 2
        elif self.level == 2 or self.level == 13 or self.level == 21:
            return 3
        elif self.level == 3 or self.level == 22 or self.level == 31:
            return 4
        elif self.level == 33:
            return 5
        elif self.level == 23:
            return 6

    def get_damage(self):
        if self.level == 0:
            return 5
        elif self.level == 1:
            return 15
        elif self.level == 21:
            return 8
        elif self.level == 11:
            return 35
        elif self.level == 12:
            return 15
        elif self.level == 23:
            return 13
        elif self.level == 33:
            return 45
        elif self.level == 13:
            return 50
        elif self.level == 2:
            return 6
        elif self.level == 22:
            return 10
        elif self.level == 3:
            return 16
        elif self.level == 31:
            return 35
        elif self.level == 32:
            return 30
