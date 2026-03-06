from .coord import Coord, headquarter_coord, neighbor, is_in_map, is_ant_can_go, distance
from .gamedata import Ant


class Pheromone:
    value: list[list[float]] = []

    @staticmethod
    def tau_base() -> float:
        return 10.0

    @staticmethod
    def decay_rate() -> float:
        return 0.97

    def decay(self) -> None:
        _lambda = Pheromone.decay_rate()
        for i in range(19):
            for j in range(19):
                self.value[i][j] = _lambda * self.value[i][j] + (1 - _lambda) * Pheromone.tau_base()

    def pheromone_of_neighbors(self, coord: Coord) -> list[float]:
        return list(
            map(
                lambda c: self.value[c.x][c.y] if is_in_map(c) else -10.0,
                map(lambda dir: neighbor(coord, dir), range(6)),
            )
        )

    def multiplier_of_neighbors(self, coord: Coord, target: Coord) -> list[float]:
        return list(
            map(
                lambda delta_dis: [1.25, 1.00, 0.75][delta_dis + 1],
                map(
                    lambda c: distance(c, target) - distance(coord, target),
                    map(lambda dir: neighbor(coord, dir), range(6)),
                ),
            )
        )

    def next_move_direction(self, ant: Ant) -> int:
        last_pos = ant.path[-2] if len(ant.path) > 1 else ant.coord
        valid = list(
            map(
                lambda c: is_ant_can_go(c) and c != last_pos,
                map(lambda dir: neighbor(ant.coord, dir), range(6)),
            )
        )
        tau = self.pheromone_of_neighbors(ant.coord)
        eta = self.multiplier_of_neighbors(ant.coord, headquarter_coord(1 - ant.player))

        max_dir, max_p = 0, -1000
        for i in range(6):
            if valid[i]:
                p = tau[i] * eta[i]
                if p > max_p:
                    max_dir, max_p = i, p
                elif p == max_p:
                    if tau[i] > tau[max_dir]:
                        max_dir, max_p = i, p
        return max_dir

    def modify_path(self, path: list[Coord], delta: float) -> None:
        for coord in set(path):
            self.value[coord.x][coord.y] = max(0.0, self.value[coord.x][coord.y] + delta)

    @staticmethod
    def success_ant_gain() -> float:
        return 10.0

    def modify_by_success_ant(self, ant: Ant) -> None:
        self.modify_path(ant.path, Pheromone.success_ant_gain())

    @staticmethod
    def failed_ant_gain() -> float:
        return -5.0

    def modify_by_failed_ant(self, ant: Ant) -> None:
        self.modify_path(ant.path, Pheromone.failed_ant_gain())

    @staticmethod
    def too_old_ant_gain() -> float:
        return -3.0

    def modify_by_too_old_ant(self, ant: Ant) -> None:
        self.modify_path(ant.path, Pheromone.too_old_ant_gain())


def generate_init_pheromone(seed: int) -> tuple[Pheromone, Pheromone]:
    lcg_seed = seed

    def lcg():
        nonlocal lcg_seed
        lcg_seed = (25214903917 * lcg_seed) & ((1 << 48) - 1)
        return lcg_seed

    def generate() -> Pheromone:
        p = Pheromone()
        p.value = [
            [(lcg() * pow(2, -46) + 8) for j in range(19)] for i in range(19)
        ]
        return p

    return generate(), generate()
