from __future__ import annotations

import enum
import itertools
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import pygame
import yaml
from pygame.event import Event
from pygame.surface import Surface

CONFIG = yaml.safe_load(open("config.yaml"))
DIFFICULTIES = CONFIG["difficulties"]
MUSIC = CONFIG["music"]
KEY_BINDINGS = CONFIG["key_bindings"]
MOUSE_BINDINGS = CONFIG["mouse_bindings"]
TILESET = CONFIG["tileset"]


def main() -> NoReturn:
    pygame.init()
    view = MinesweeperView()
    solver_enabled = False

    while True:
        ev = pygame.event.get()
        for event in ev:
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONUP:
                view.handle_click(event)
            if event.type == pygame.KEYUP:
                view.handle_keyup(event)
                if event.key == pygame.K_s:
                    solver_enabled = not solver_enabled
        view.redraw()  # for clock update
        if solver_enabled:
            solver = MinesweeperSolver(view.minesweeper)
            soln = solver.solve_one()
            if soln is not None:
                if soln["action"] == "flag":
                    for coord in soln["coords"]:
                        view.minesweeper.toggle_flag(*coord)
                elif soln["action"] == "reveal":
                    for coord in soln["coords"]:
                        view.minesweeper.reveal(*coord)
        pygame.time.wait(50)


@enum.unique
class MinesweeperState(enum.Enum):
    pregame = 0
    in_progress = 1
    game_won = 2
    game_lost = 3

    @classmethod
    def end_states(cls) -> set[MinesweeperState]:
        return {cls.game_won, cls.game_lost}


@dataclass
class Square:
    revealed: bool = False
    is_mine: bool = False
    hit: bool = False
    flagged: bool = False
    bordering: int = 0


class Minesweeper:
    def __init__(self, width: int, height: int, mines: int):
        if mines >= width * height:
            raise ValueError("too many mines!")
        self.width = width
        self.height = height
        self.mines = mines
        self.state = MinesweeperState.pregame
        self._squares = {(x, y): Square() for x in range(width) for y in range(height)}
        self.remaining = width * height - mines
        self.flag_remaining = mines
        pygame.mixer.music.stop()

    def __str__(self) -> str:
        row_strs = []
        for y in range(self.height):
            row_str = ""
            for x in range(self.width):
                square = self._squares[x, y]
                if square.revealed:
                    if square.is_mine:
                        row_str += "x"
                    else:
                        row_str += str(square.bordering)
                else:
                    if square.flagged:
                        row_str += "F"
                    else:
                        row_str += "."
            row_strs.append(row_str)
        return "\n".join(row_strs)

    def reveal(self, x: int, y: int) -> None:
        if self.state in MinesweeperState.end_states():
            return
        if self.state is MinesweeperState.pregame:
            self._init_mines(x, y)
            self.state = MinesweeperState.in_progress
            if MUSIC["enabled"]:
                pygame.mixer.music.load(MUSIC["in_game"])
                pygame.mixer.music.play(-1)
        square = self._squares[x, y]
        if square.revealed or square.flagged:
            return
        square.revealed = True
        if square.is_mine:
            square.hit = True
            self.state = MinesweeperState.game_lost
            if MUSIC["enabled"]:
                pygame.mixer.music.load(MUSIC["gameover"])
                pygame.mixer.music.play()
            self._reveal_all()
            return
        if square.bordering == 0:
            for x, y in self._get_bordering(x, y):
                self.reveal(x, y)
        self.remaining -= 1
        if self.remaining == 0:
            self._reveal_all()
            self.state = MinesweeperState.game_won
            if MUSIC["enabled"]:
                pygame.mixer.music.load(MUSIC["victory"])
                pygame.mixer.music.play()

    def burst_reveal(self, x: int, y: int) -> None:
        if self.state in MinesweeperState.end_states():
            return
        square = self._squares[x, y]
        if not square.revealed:
            return
        border_flags = 0
        border_pos = self._get_bordering(x, y)
        for pos in border_pos:
            if self._squares[pos].flagged:
                border_flags += 1
        if square.bordering == border_flags:
            for pos in border_pos:
                self.reveal(*pos)

    def toggle_flag(self, x: int, y: int) -> None:
        if self.state in MinesweeperState.end_states():
            return
        square = self._squares[x, y]
        if square.revealed:
            return
        if square.flagged:
            self.flag_remaining += 1
        else:
            self.flag_remaining -= 1
        square.flagged = not square.flagged

    def _init_mines(self, safe_x: int, safe_y: int) -> None:
        squares = list(self._squares.keys())
        squares.remove((safe_x, safe_y))
        for x, y in random.sample(squares, self.mines):
            self._squares[x, y].is_mine = True
            for pos in self._get_bordering(x, y):
                self._squares[pos].bordering += 1

    def _reveal_all(self) -> None:
        for square in self._squares.values():
            square.revealed = True

    def _get_bordering(
        self, x: int, y: int, include_self: bool = False
    ) -> set[tuple[int, int]]:
        border_set = set()
        for i in range(max(0, x - 1), min(self.width, x + 2)):
            for j in range(max(0, y - 1), min(self.height, y + 2)):
                if i != x or j != y or include_self:
                    border_set.add((i, j))
        return border_set


class MinesweeperView:
    def __init__(self, difficulty: str = "easy", tileset: str = "small"):
        self.start_time: float | None
        self.end_time: float | None
        self.screen: Surface
        self.minesweeper: Minesweeper
        self.tileset = tileset
        self.difficulty = difficulty
        self.screen = self.get_screen()
        self.start_new_game()

    def start_new_game(self) -> None:
        self.minesweeper = Minesweeper(**DIFFICULTIES[self.difficulty])
        self.start_time = None
        self.end_time = None
        self.redraw()

    def redraw(self) -> None:
        if self.screen is None:
            self.screen = self.get_screen()
        light_gray = 239, 239, 237
        black = 0, 0, 0
        self.screen.fill(light_gray)
        tile_px = TILESET[self.tileset]["tile_px"]
        for i in range(self.minesweeper.width):
            for j in range(self.minesweeper.height):
                rect = (tile_px * i, tile_px * j)
                square = self.minesweeper._squares[i, j]
                if square.flagged:
                    if (
                        self.minesweeper.state in MinesweeperState.end_states()
                        and not square.is_mine
                    ):
                        tile_name = "mine_hit"
                    else:
                        tile_name = "flag"
                elif square.revealed:
                    if square.is_mine:
                        if square.hit:
                            tile_name = "mine_hit"
                        else:
                            tile_name = "mine"
                    else:
                        tile_name = str(square.bordering)
                else:
                    tile_name = "unexplored"
                self.screen.blit(self.tiles[tile_name], rect)

        font_px = TILESET[self.tileset]["font_px"]
        font = pygame.font.SysFont("Consolas", font_px, bold=1)
        flag_remaining = font.render(str(self.minesweeper.flag_remaining), True, black)
        self.screen.blit(
            self.tiles["flag"],
            (0.5 * tile_px, (self.minesweeper.height + 0.5) * tile_px),
        )
        self.screen.blit(
            flag_remaining,
            (1.8 * tile_px, (self.minesweeper.height + 1) * tile_px - font_px / 2),
        )
        if self.start_time is None:
            seconds = 0
        elif self.minesweeper.state in MinesweeperState.end_states():
            if self.end_time is None:
                self.end_time = time.time()
            seconds = int(self.end_time - self.start_time)
        else:
            seconds = int(time.time() - self.start_time)
        time_elapsed = font.render(str(seconds), True, black)
        self.screen.blit(
            self.tiles["clock"],
            (
                (self.minesweeper.width - 3) * tile_px,
                (self.minesweeper.height + 0.5) * tile_px,
            ),
        )
        self.screen.blit(
            time_elapsed,
            (
                (self.minesweeper.width - 1.7) * tile_px,
                (self.minesweeper.height + 1) * tile_px - font_px / 2,
            ),
        )

        if self.minesweeper.state is MinesweeperState.game_won:
            face_tile = self.tiles["win"]
        elif self.minesweeper.state is MinesweeperState.game_lost:
            face_tile = self.tiles["lose"]
        else:
            face_tile = self.tiles["normal"]
        self.screen.blit(
            face_tile,
            (
                (self.minesweeper.width - 1) * tile_px / 2,
                (self.minesweeper.height + 0.5) * tile_px,
            ),
        )

        pygame.display.flip()

    def handle_click(self, event: Event) -> None:
        mouse_x, mouse_y = event.pos
        tile_px = TILESET[self.tileset]["tile_px"]
        i = int(mouse_x / tile_px)
        j = int(mouse_y / tile_px)
        if i >= self.minesweeper.width or j >= self.minesweeper.height:
            return
        if event.button == MOUSE_BINDINGS["reveal"]:
            if self.minesweeper.state is MinesweeperState.pregame:
                self.start_time = time.time()
            self.minesweeper.reveal(i, j)
        elif event.button == MOUSE_BINDINGS["burst_reveal"]:
            self.minesweeper.burst_reveal(i, j)
        elif event.button == MOUSE_BINDINGS["flag"]:
            self.minesweeper.toggle_flag(i, j)
        self.redraw()

    def handle_keyup(self, event: Event) -> None:
        if event.key == getattr(pygame, KEY_BINDINGS["new_game"]):
            self.start_new_game()
        elif event.key == getattr(pygame, KEY_BINDINGS["difficulty_1"]):
            self.difficulty = "easy"
        elif event.key == getattr(pygame, KEY_BINDINGS["difficulty_2"]):
            self.difficulty = "medium"
        elif event.key == getattr(pygame, KEY_BINDINGS["difficulty_3"]):
            self.difficulty = "hard"
        elif event.key == getattr(pygame, KEY_BINDINGS["difficulty_4"]):
            self.difficulty = "ultimate"
        elif event.key == getattr(pygame, KEY_BINDINGS["small_tiles"]):
            self.tileset = "small"
            self.redraw()
        elif event.key == getattr(pygame, KEY_BINDINGS["large_tiles"]):
            self.tileset = "large"
            self.redraw()
        elif event.key == getattr(pygame, KEY_BINDINGS["click_swap"]):
            MOUSE_BINDINGS["reveal"], MOUSE_BINDINGS["flag"] = (
                MOUSE_BINDINGS["flag"],
                MOUSE_BINDINGS["reveal"],
            )
        elif event.key == getattr(pygame, KEY_BINDINGS["print_console"]):
            print(self.minesweeper)
        elif event.key == getattr(pygame, KEY_BINDINGS["help"]):
            solver = MinesweeperSolver(self.minesweeper)
            soln = solver.solve_one()
            if soln is not None:
                if soln["action"] == "flag":
                    self.minesweeper.toggle_flag(*next(iter(soln["coords"])))
                elif soln["action"] == "reveal":
                    self.minesweeper.reveal(*next(iter(soln["coords"])))

    @property
    def difficulty(self) -> str:
        return self._difficulty

    @difficulty.setter
    def difficulty(self, value: str) -> None:
        if getattr(self, "difficulty", None) == value:
            return
        self._difficulty = value
        pygame.display.set_caption(f"Minesweeper [{self.difficulty}]")
        self.screen = None
        self.start_new_game()

    @property
    def tileset(self) -> str:
        return self._tileset

    @tileset.setter
    def tileset(self, value: str) -> None:
        if getattr(self, "tileset", None) == value:
            return
        self._tileset = value
        directory = TILESET[self.tileset]["dir"]
        self.tiles = {
            file.stem: pygame.image.load(file) for file in Path(directory).glob("*.png")
        }
        self.screen = None

    def get_screen(self) -> Surface:
        tile_px = TILESET[self.tileset]["tile_px"]
        size = (
            tile_px * DIFFICULTIES[self.difficulty]["width"],
            tile_px * (DIFFICULTIES[self.difficulty]["height"] + 2),
        )
        return pygame.display.set_mode(size)


class MinesweeperSolver:
    def __init__(self, minesweeper: Minesweeper):
        self.minesweeper = minesweeper

    def _add_leasts(
        self, at_least: dict[frozenset, int], coords: tuple | frozenset, mines: int
    ) -> None:
        if mines < 2 or len(coords) == mines or len(coords) < 3:
            return

        for sub_coords in itertools.combinations(coords, len(coords) - 1):
            at_least[frozenset(sub_coords)] = mines - 1
            self._add_leasts(at_least, sub_coords, mines - 1)

    def solve_one(self) -> dict[str, str | frozenset] | None:
        m = self._init_m(self.minesweeper)

        at_least: dict[frozenset, int] = dict()
        at_least_free: dict[frozenset, int] = dict()
        for coords, mines in m.items():
            self._add_leasts(at_least, coords, mines)
            self._add_leasts(at_least_free, coords, len(coords) - mines)

        prev_size = None
        while len(m) + len(at_least) + len(at_least_free) != prev_size:
            prev_size = len(m) + len(at_least) + len(at_least_free)
            to_add: dict[frozenset, int] = {}
            for coords1, mines1 in m.items():
                for coords2, mines2 in m.items():
                    if coords1 is not coords2:
                        result = self._get_diffs(
                            coords1, mines1, coords2, mines2, m, to_add
                        )
                        if result:
                            return result
                        result = self._get_diffs(
                            coords2, mines2, coords1, mines1, m, to_add
                        )
                        if result:
                            return result
                result = self._get_leasts(
                    coords1, mines1, at_least, at_least_free, "reveal"
                )
                if result:
                    return result
                free1 = len(coords1) - mines1
                result = self._get_leasts(
                    coords1, free1, at_least_free, at_least, "flag"
                )
                if result:
                    return result
            for i, j in to_add.items():
                m[i] = j
        return None
        # for coords, mines in m.items():
        #     self._add_leasts(at_least, coords, mines)
        #     self._add_leasts(at_least_free, coords, len(coords) - mines)

    @staticmethod
    def _init_m(minesweeper: Minesweeper) -> dict[frozenset, int]:
        m: dict[frozenset, int] = {frozenset(): 0}
        for coord, square in minesweeper._squares.items():
            if square.revealed and square.bordering > 0:
                border_coords = minesweeper._get_bordering(*coord)
                unrevealed = set()
                flagged = set()
                for border_coord in border_coords:
                    border_square = minesweeper._squares[border_coord]
                    if border_square.revealed:
                        pass
                    elif border_square.flagged:
                        flagged.add(border_coord)
                    else:
                        unrevealed.add(border_coord)
                if len(unrevealed) > 0:
                    mines_unflagged = square.bordering - len(flagged)
                    m[frozenset(unrevealed)] = mines_unflagged
        return m

    @staticmethod
    def _get_diffs(
        coords1: frozenset,
        mines1: int,
        coords2: frozenset,
        mines2: int,
        m: dict[frozenset, int],
        to_add: dict[frozenset, int],
    ) -> dict[str, str | frozenset] | None:
        if coords1.issuperset(coords2):
            diff_coords = coords1 - coords2
            diff_mines = mines1 - mines2
            if diff_coords:
                if len(diff_coords) == diff_mines:
                    return {"action": "flag", "coords": diff_coords}
                if diff_mines == 0:
                    return {"action": "reveal", "coords": diff_coords}
                if diff_coords not in m:
                    to_add[frozenset(diff_coords)] = diff_mines
        return None

    def _get_leasts(
        self,
        coords1: frozenset,
        count1: int,
        at_least: dict[frozenset, int],
        at_least2: dict[frozenset, int],
        action: str,
    ) -> dict[str, str | frozenset] | None:
        for coords2, count2 in at_least.items():
            if coords1.issuperset(coords2):
                diff_coords = coords1 - coords2
                diff_count = count1 - count2
                if diff_coords:
                    if diff_count == 0:
                        return {"action": action, "coords": diff_coords}
                    elif diff_count != len(diff_coords):
                        self._add_leasts(
                            at_least2, diff_coords, len(diff_coords) - diff_count
                        )
        return None


if __name__ == "__main__":
    raise SystemExit(main())
