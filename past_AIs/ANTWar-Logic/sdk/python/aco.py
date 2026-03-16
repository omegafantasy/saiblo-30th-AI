from math import sqrt
from protocol import *
from ant import Ant
import random
from enum import Enum
class State(Enum):
    Alive = 0  
    Success = 1
    Fail = 2
    TooOld = 3
    Frozen = 4
    NotGenerated = 5
    Available = 6
    TimeOut = 7
    GotByPlayer0 = 8
    GotByPlayer1 = 9
Q0 = 10
Q1 = 10
Q2 = -5
Q3 = -3
P0 = 0.0
BETA = 5
ALPHA = 1
GLOBAL_R = 0.9
LOCAL_R = 0.9
LOCAL_PHE = 1.0
ACC = 1000
phe_init = 1
age_limit = 32
d = [[(0, 1), (-1, 0), (0, -1), (1, -1), (1, 0), (1, 1)],
                        [(-1, 1), (-1, 0), (-1, -1), (0, -1), (1, 0), (0, 1)]]
camp_pos = [Pos(2, 9),Pos(16, 9)]
# pheromon map
# pheromon = [[[[phe_init for i in range(6)] for i in range(2)] for i in range(35)] for i in range(35)]
# print(pheromon)

def random_pick(some_list, probabilities):
    x = random.uniform(0,1)
    cumulative_probability = 0.0
    for item, item_probability in zip(some_list, probabilities):
         cumulative_probability += item_probability
         if x < cumulative_probability:
               break
    return item 

def is_valid(a: Pos):
    # if a.y < 0 or a.y >= 19 :
    #     return False
    # # Calculate valid range for x from y
    # base = abs((a.y + 1) - 9) / 2
    # max_offset = 19 - abs(a.y - 9) -1
    return distance(a, Pos(9, 9)) <= 9 # valid range for x: [base, base + max_offset]


# def distance(a: Pos, b: Pos):
#     dy = abs(a.y - b.y)
#     dx = 0
#     if abs(a.y - b.y) % 2:
#         if a.x > b.x:
#             dx = max(0, abs(a.x - b.x) - abs(a.y - b.y) / 2 - (a.y % 2))
#         else:
#             dx = max(0, abs(a.x - b.x) - abs(a.y - b.y) / 2 - (1 - (a.y % 2)))
#     else:
#         dx = max(0, abs(a.x - b.x) - abs(a.y - b.y) / 2)
#     return dx + dy

class Hex():
    def __init__(self, x, y) -> None:
        self.q = x
        self.r = y
def axialDistance(a: Hex, b: Hex):
    return (abs(a.q - b.q) + abs(a.q + a.r - b.q - b.r) + abs(a.r - b.r)) / 2


def distance(a: Pos, b: Pos):
    return int(axialDistance(evenq2axial(a), evenq2axial(b)))


def evenq2axial(hex: Pos):
  q = hex.y
  r = hex.x - (hex.y + (hex.y & 1)) / 2
  return Hex(q, r)


