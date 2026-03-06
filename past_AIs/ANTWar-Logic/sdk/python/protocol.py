from enum import Enum
class OperationType(Enum):
    unlimit_coins = 93
    build_tower = 11
    upgrade_tower = 12
    destory_tower = 13
    use_item_1 = 21
    use_item_2 = 22
    use_item_3 = 23
    use_item_4 = 24
    upgrade_base_speed = 31
    upgrade_ant_hp = 32
    
class Operation():
    def __init__(self, operation_type:OperationType, args_1:int = None, args_2:int = None):
        self.operation_type = operation_type
        self.args_1 = args_1
        self.args_2 = args_2
    def dumps(self) -> str:
        if self.args_2 is not None:
            return "{} {} {}\n".format(self.operation_type.value, self.args_1, self.args_2)
        elif self.args_1 is not None:
            return "{} {}\n".format(self.operation_type.value, self.args_1)
        else:
            return "{}\n".format(self.operation_type.value)
class Pos:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
# class OP:
#     def __init__(self, type=None, id=None, x=None, y=None, arg=None):
#         self.type = type
#         self.id = id
#         self.x = x
#         self.y = y
#         self.arg = arg

#     def dumps(self) -> str:
#         pass

# class set_point(OP):
#     def __init__(self, x, y):
#         super().__init__(type, x=x, y=y)

#     def dumps(self) -> str:
#         return "0 {} {}\n".format(self.x, self.y)

# class set_ant(OP):
#     def __init__(self, id):
#         super().__init__(type, id=id)

#     def dumps(self) -> str:
#         return "1 {}\n".format(self.id)

# class build_tower(OP):
#     def __init__(self, x, y):
#         super().__init__(type, x=x, y=y)

#     def dumps(self) -> str:
#         return "2 {} {}\n".format(self.x, self.y)

# class update_tower(OP):
#     def __init__(self, id, arg):
#         super().__init__(type, id=id, arg=arg)

#     def dumps(self) -> str:
#         return "3 {} {}\n".format(self.id, self.arg)

# class destory_tower(OP):
#     def __init__(self, id):
#         super().__init__(type, id=id)

#     def dumps(self) -> str:
#         return "4 {}\n".format(self.id)

# class build_barrack(OP):
#     def __init__(self, x, y):
#         super().__init__(type, x=x, y=y)

#     def dumps(self) -> str:
#         return "5 {} {}\n".format(self.x, self.y)

# class destory_barrack(OP):
#     def __init__(self, id):
#         super().__init__(type, id=id)

#     def dumps(self) -> str:
#         return "6 {}\n".format(self.id)


