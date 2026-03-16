
## 1. `rawio`

提供AI编写指南中所提到的输入输出协议支持。

- `write_to_judger`：将信息通过4+N协议转化后再输出。
- `debug`：实际上是向标准错误流输出信息。这些信息被作为调试信息呈现在saiblo评测结果页面中。

```python

from antwar import rawio


def write_to_judger(msg: str) -> None


  def debug(msg: str) -> None
```

## 2. `coord`
提供坐标相关的帮助函数。

- `Coord`：描述坐标的简单结构体
- `is_in_map`：是否在地图中。
- `is_ant_can_go`：是否为蚂蚁可以移动的位置。等价于is_in_map(c) && !is_highland()
- `is_highland`：是否为高台，也即蚂蚁无法行动的区域。
- `is_player_highland`：是否为对应玩家控制的/可以建造防御塔的高台。
- `distance`：计算两坐标之间的距离。即两点之间最短路径的长度。相同点之间的距离定义为0。
- `neighbor`：计算坐标对应方向的相邻点的坐标。

```python

from antwar import coord


class Coord:
  x: int
  y: int


def is_in_map(coord: Coord) -> bool


  def is_ant_can_go(coord: Coord) -> bool


  def is_highland(coord: Coord) -> bool


  def is_player_highland(coord: Coord, player: int) -> bool


def distance(c0: Coord, c1: Coord) -> int


  def neighbor(coord: Coord, direction: int) -> Coord
```

## 3. `gamedata`
提供对蚂蚁、防御塔、超级武器的相关封装。
- `Ant`：蚂蚁
  - `id`：编号，从0开始。
  - `player`：所属玩家。
  - `hp` `maxhp` `level`：蚂蚁的当前生命值，最大生命值，等级。
  - `age`：蚂蚁的年龄。
  - `evasion_count`：蚂蚁剩余的“紧急回避”次数。
  - `state`：蚂蚁的状态
  - `path`：蚂蚁经过的路径点的列表。
- `Tower`：防御塔
  - `id`：编号，从0开始。
  - `player`：所属玩家。
  - `type`：`TowerType` 防御塔的类型
  - `cd`：防御塔冷却。若为0，说明冷却完成，当回合可以攻击。
- `SuperWeapon`：超级武器
  - `player`：所属玩家。
  - `type`：`SuperWeaponType` 超级武器类型。
  - `duration`：超级武器持续时间，大于0为还在生效。
  - `coord`：部署坐标。

```python

from antwar import gamedata


class AntState(IntEnum):
  Alive = 0
  Success = 1
  Fail = 2
  TooOld = 3
  Frozen = 4


class Ant:
  id: int
  player: int
  hp: int
  maxhp: int
  level: int
  age: int
  evasion_count: int
  state: AntState
  path: list[Coord]


class TowerType(IntEnum):
  Basic = 0
  Heavy = 1
  HeavyPlus = 11
  Ice = 12
  Cannon = 13
  Quick = 2
  QuickPlus = 21
  Double = 22
  Sniper = 23
  Mortor = 3
  MortorPlus = 31
  Pulse = 32
  Missile = 33


class Tower:
  id: int
  player: int
  type: TowerType
  cd: int


class SuperWeaponType(IntEnum):
  LightningStorm = 1
  EMPBlaster = 2
  Deflectors = 3
  EmergencyEvasion = 4


class SuperWeapon:
  player: int
  type: SuperWeaponType
  duration: int
  coord: Coord
```

## 4. `protocol`

```python

from antwar import protocol


class InitInfo():
  self_player: int
  seed: int


def read_init_info() -> InitInfo


class OperationType(IntEnum):
  BuildTower = 11
  UpgradeTower = 12
  DowngradeTower = 13
  DeployLightningStorm = 21
  DeployEMPBlaster = 22
  DeployDeflector = 23
  DeployEmergencyEvasion = 24
  UpgradeGenerateSpeed = 31
  UpgradeAntMaxHP = 32


class Operation:
  type: OperationType
  arg0: int
  arg1: int


def build_tower_op(coord: Coord) -> Operation


  def upgrade_tower_op(id: int, type: TowerType) -> Operation


  def downgrade_tower_op(id: int) -> Operation


  def deploy_super_weapon(type: SuperWeaponType, coord: Coord) -> Operation


  def upgrade_generate_speed_op() -> Operation


  def upgrade_ant_maxhp_op() -> Operation


def read_enemy_operations() -> list[Operation]


  def write_our_operation(ops: list[Operation]) -> None


class RoundInfo:
  ants: list[Ant]
  towers: list[Tower]
  coin: [int, int]
  hp: [int, int]


def read_round_info() -> RoundInfo
```

## 5. `pheromone`

```python

from antwar import pheromone


class Pheromone:
  value: list[list[float]]

  def init(seed: int) -> None

  def decay_rate() -> float

    def decay() -> None

  def pheromone_of_neighbours(coord: Coord) -> list[float]

    def multiplier_of_neighbours(coord: Coord, target: Coord) -> list[float]

    def next_move_direction(ant: Ant) -> int

  def modify_path(path: list[Coord], delta: float) -> None

    def modify_by_success_ant(ant: Ant) -> None

    def modify_by_failed_ant(ant: Ant) -> None

    def modify_by_too_old_ant(ant: Ant) -> None
```

## 6. `gamestate`

```python
class GameState:
    ants: list[Ant]
    towers: list[Tower]
    coin: [int, int]
    hp: [int, int]
    active_super_weapon: list[SuperWeapon]
    phero: [Pheromone, Pheromone]
    gen_speed_lv: [int, int]
    ant_maxhp_lv: [int, int]
    
    next_ant_id: int
    next_tower_id: int
    
    def ant_idx_of_id(id: int) -> int
    def ant_of_id(id: int) -> Optional[Ant]
    def ant_at(coord: Coord) -> list[Ant]
    
    def tower_idx_of_id(id: int) -> int
    def tower_of_id(id: int) -> Optional[Tower]
    def tower_at(coord: Coord) -> Optional[Tower]
    
    def build_tower(player: int, coord: Coord) -> Optional[Tower]
    def upgrade_tower(id: int, type: TowerType) -> Optional[Tower]
    def downgrade_tower(id: int) -> Optional[Tower]
    
    def build_tower_cost(player: int) -> int
    def upgrade_tower_cost(id: int, type: TowerType) -> int
    def downgrade_tower_income(id: int) -> int
    
    def upgrade_generate_speed(player: int) -> bool
    def upgrade_ant_maxhp(player: int) -> bool
    
    def upgrade_generate_speed_cost(player: int) -> int
    def upgrade_ant_maxhp_cost(player: int) -> int
    
    def set_coin(player: int, new_coin: int) -> None
    def update_coin(player: int, delta: int) -> None
    
    def set_hp(player: int, new_hp: int) -> None
    def update_hp(player: int, delta: int) -> None
    
    def pheromone_decay() -> None
    
    def is_operation_valid(player: int, op: Operation) -> bool
    def apply_operation(player: int, op: Operation) -> bool
```

## 7. `controller`

```python

from antwar import controller


class GameController:
  round: int
  self_player: int
  game_state: GameState

  def init() -> None

  def read_enemy_ops() -> list[Operation]

    def apply_enemy_ops(ops: list[Operation]) -> bool

    def read_and_apply_enemy_ops() -> bool

  def try_apply_our_op(op: Operation) -> bool

    def try_apply_our_ops(op: list[Operation]) -> bool

    def finish_and_send_our_ops() -> None

  def read_and_apply_round_info() -> RoundInfo

  def simulate_next_round() -> bool


def run_antwar_ai(ai_func: Callable[[GameState], list[Operations]]) -> None


  def run_antwar_ai(
          ai0_func: Callable[[GameState], list[Operations]],
          ai1_func: Callable[[GameState], list[Operations]]) -> None
```

Without run_antwar_ai

```python
import * from controller


def make_decision_for_player_0(game: GameController) -> list[Operation]:


# User code

def make_decision_for_player_0(game: GameController) -> list[Operation]:


# User code

game = GameController()
game.init()

while (True):
  if game.my_seat == 0:
    ops = make_decision_for_player0(game)
    game.try_apply_our_operations(ops)
    game.finish_and_send_our_operations()

    game.read_and_apply_enemy_operations()

    game.finish_and_send_our_ops()
  else:
    game.read_and_apply_enemy_operations()

    ops = make_decision_for_player1(game)
    game.try_apply_our_operations(ops)
    game.finish_and_send_our_operations()

    game.finish_and_send_our_ops()
```