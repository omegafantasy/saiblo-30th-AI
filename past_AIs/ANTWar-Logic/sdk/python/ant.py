class Ant:
    def __init__(self, x:int, y:int):
        self.id = 0
        self.hp = 10
        self.x = x
        self.y = y
        self.path = []
        self.age = 0
        self.state = 0
        self.player = 0
        self.protection = 0
        self.frozen = 0
        self.max_hp = 10
