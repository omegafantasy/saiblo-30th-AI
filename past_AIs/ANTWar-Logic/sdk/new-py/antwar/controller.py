from typing import Callable

from .gamestate import GameState
from .protocol import read_init_info, Operation, write_our_operation, RoundInfo, read_round_info, read_enemy_operations


class GameController:
    my_seat: int = 0
    game_state: GameState = GameState()
    my_operation_list: list[Operation] = []

    def init(self) -> None:
        init_info = read_init_info()
        self.my_seat = init_info.my_seat
        self.game_state.init_with_seed(init_info.seed)

    def read_enemy_ops(self) -> list[Operation]:
        return read_enemy_operations()

    def apply_enemy_ops(self, ops: list[Operation]) -> bool:
        for op in ops:
            if not self.game_state.apply_operation(1 - self.my_seat, op):
                return False
        return True

    def read_and_apply_enemy_ops(self) -> bool:
        return self.apply_enemy_ops(self.read_enemy_ops())

    def try_apply_our_op(self, op: Operation) -> bool:
        if self.game_state.apply_operation(self.my_seat, op):
            self.my_operation_list.append(op)
            return True
        return False

    def try_apply_our_ops(self, ops: list[Operation]) -> bool:
        for op in ops:
            if not self.try_apply_our_op(op):
                return False
        return True

    def finish_and_send_our_ops(self) -> None:
        write_our_operation(self.my_operation_list)
        self.my_operation_list = []

    def next_round(self) -> RoundInfo:
        round_info = read_round_info()
        self.game_state.simulate_next_round()
        return round_info


def run_antwar_ai(ai_func: Callable[[int, GameState], list[Operation]]) -> None:
    game = GameController()
    game.init()
    while True:
        if game.my_seat == 0:
            ops = ai_func(0, game.game_state)
            game.try_apply_our_ops(ops)
            game.finish_and_send_our_ops()

            game.read_and_apply_enemy_ops()
        else:
            game.read_and_apply_enemy_ops()

            ops = ai_func(1, game.game_state)
            game.try_apply_our_ops(ops)
            game.finish_and_send_our_ops()

        game.next_round()
