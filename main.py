import enum
import pygame
import random
import os
import sys
import time


def main():
    view = MinesweeperView()
    while True:
        ev = pygame.event.get()
        for event in ev:
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.MOUSEBUTTONUP:
                view.handle_click(event)
            if event.type == pygame.KEYUP:
                view.handle_keyup(event)
        view.redraw() # for clock update


@enum.unique
class Difficulty(enum.Enum):
    easy = {
        'width': 9,
        'height': 9,
        'mines': 10,
    }
    medium = {
        'width': 16,
        'height': 16,
        'mines': 40,
    }
    hard = {
        'width': 30,
        'height': 16,
        'mines': 99,
    }


@enum.unique
class Tileset(enum.Enum):
    small = {
        'dir': 'img_small/',
        'tile_px': 21
    }
    large = {
        'dir': 'img/',
        'tile_px': 61
    }


class MinesweeperView(object):

    def __init__(self, difficulty=Difficulty.easy, tileset=Tileset.small):
        self._set_difficulty(difficulty, init=True)
        self._set_tileset(tileset, init=True)
        self.start_new_game()

    def start_new_game(self):
        self.minesweeper = Minesweeper(**self.difficulty.value)
        self.start_time = None
        self.end_time = None
        self.redraw()

    def redraw(self):
        if self.screen is None:
            self._init_screen()
        black = 0, 0, 0
        white = 255, 255, 255
        self.screen.fill(black)
        tile_px = self.tileset.value['tile_px']
        for i in range(self.minesweeper.width):
            for j in range(self.minesweeper.height):
                rect = (tile_px * i, tile_px * j)
                square = self.minesweeper._squares[i, j]
                if square.flagged:
                    tile_name = 'flag'
                elif square.revealed:
                    if square.is_mine:
                        if square.hit:
                            tile_name = 'mine_hit'
                        else:
                            tile_name = 'mine'
                    else:
                        tile_name = str(square.bordering)
                else:
                    tile_name = 'unexplored'
                self.screen.blit(self.tiles[tile_name], rect)

        font = pygame.font.SysFont('Consolas', 15, bold=1)
        flag_remaining = font.render(str(self.minesweeper.flag_remaining), 1, white)
        self.screen.blit(
            self.tiles['flag'], (40-21-10, self.minesweeper.height * tile_px + 15 - 3))
        self.screen.blit(
            flag_remaining, (40, self.minesweeper.height * tile_px + 15))
        if self.start_time is None:
            seconds = 0
        elif self.minesweeper.state in MinesweeperState.end_states():
            if self.end_time is None:
                self.end_time = time.time()
            seconds = int(self.end_time - self.start_time)
        else:
            seconds = int(time.time() - self.start_time)
        time_elapsed = font.render(str(seconds), 1, white)
        self.screen.blit(
            self.tiles['clock'], (150-21-10, self.minesweeper.height * tile_px + 15 - 3))
        self.screen.blit(
            time_elapsed, (150, self.minesweeper.height * tile_px + 15))

        pygame.display.flip()

    def handle_click(self, event):
        mouse_x, mouse_y = event.pos
        tile_px = self.tileset.value['tile_px']
        i = int(mouse_x / tile_px)
        j = int(mouse_y / tile_px)
        if i >= self.minesweeper.width or j >= self.minesweeper.height:
            return
        if event.button == 1:
            if self.minesweeper.state is MinesweeperState.pregame:
                self.start_time = time.time()
            self.minesweeper.reveal(i, j)
        elif event.button == 2:
            self.minesweeper.burst_reveal(i, j)
        elif event.button == 3:
            self.minesweeper.toggle_flag(i, j)
        self.redraw()

    def handle_keyup(self, event):
        if event.key == pygame.K_n:
            self.start_new_game()
        elif event.key == pygame.K_1:
            if self._set_difficulty(Difficulty.easy):
                self.start_new_game()
        elif event.key == pygame.K_2:
            if self._set_difficulty(Difficulty.medium):
                self.start_new_game()
        elif event.key == pygame.K_3:
            if self._set_difficulty(Difficulty.hard):
                self.start_new_game()
        elif event.key == pygame.K_MINUS:
            self._set_tileset(Tileset.small)
            self.redraw()
        elif event.key == pygame.K_EQUALS:
            self._set_tileset(Tileset.large)
            self.redraw()

    def _set_difficulty(self, difficulty, init=False):
        if not init and difficulty is self.difficulty:
            return False
        self.difficulty = difficulty
        self.screen = None
        pygame.display.set_caption(
            'Minesweeper [{}]'.format(self.difficulty.name))
        return True

    def _set_tileset(self, tileset, init=False):
        if not init and tileset is self.tileset:
            return
        self.tileset = tileset
        dir = self.tileset.value['dir']
        self.tiles = dict()
        for file in os.listdir(dir):
            if file.endswith('.png'):
                name = file[:-4]
                self.tiles[name] = pygame.image.load(os.path.join(dir, file))
        self.screen = None

    def _init_screen(self):
        tile_px = self.tileset.value['tile_px']
        size = (
            tile_px * self.difficulty.value['width'],
            tile_px * self.difficulty.value['height'] + 40)
        self.screen = pygame.display.set_mode(size)


@enum.unique
class MinesweeperState(enum.Enum):
    pregame = 0
    in_progress = 1
    game_won = 2
    game_lost = 3

    @classmethod
    def end_states(cls):
        return {cls.game_won, cls.game_lost}


class Square(object):

    def __init__(self):
        self.revealed = False
        self.is_mine = False
        self.hit = False
        self.flagged = False
        self.bordering = 0

    def __repr__(self):
        return '<Square(revealed={0}, is_mine={1}, bordering={2}>'.format(
            self.revealed, self.is_mine, self.bordering
        )


class Minesweeper(object):

    def __init__(self, width, height, mines):
        if mines >= width * height:
            raise ValueError('too many mines!')
        self.width = width
        self.height = height
        self.mines = mines
        self.state = MinesweeperState.pregame
        self._squares = dict(
            ((x, y), Square())
            for x in range(width)
            for y in range(height)
        )
        self.remaining = width * height - mines
        self.flag_remaining = mines

    def __str__(self):
        row_strs = []
        for y in range(self.height):
            row_str = ''
            for x in range(self.width):
                square = self._squares[x, y]
                if square.revealed:
                    if square.is_mine:
                        row_str += 'x'
                    else:
                        row_str += str(square.bordering)
                else:
                    if square.flagged:
                        row_str += 'F'
                    else:
                        row_str += '.'
            row_strs.append(row_str)
        return '\n'.join(row_strs)

    def reveal(self, x, y):
        if self.state in MinesweeperState.end_states():
            return
        if self.state is MinesweeperState.pregame:
            self._init_mines(x, y)
            self.state = MinesweeperState.in_progress
        square = self._squares[x, y]
        if square.revealed or square.flagged:
            return
        square.revealed = True
        if square.is_mine:
            square.hit = True
            self.state = MinesweeperState.game_lost
            self._reveal_all()
            return
        if square.bordering == 0:
            for x, y in self._get_bordering(x, y):
                self.reveal(x, y)
        self.remaining -= 1
        if self.remaining == 0:
            self._reveal_all()
            self.state = MinesweeperState.game_won

    def burst_reveal(self, x, y):
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

    def toggle_flag(self, x, y):
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

    def _init_mines(self, safe_x, safe_y):
        squares = set(self._squares.keys())
        squares.remove((safe_x, safe_y))
        for x, y in random.sample(squares, self.mines):
            self._squares[x, y].is_mine = True
            for pos in self._get_bordering(x, y):
                self._squares[pos].bordering += 1

    def _reveal_all(self):
        for square in self._squares.values():
            square.revealed = True

    def _get_bordering(self, x, y, include_self=False):
        border_set = set()
        for i in range(max(0, x - 1), min(self.width, x + 2)):
            for j in range(max(0, y - 1), min(self.height, y + 2)):
                if i != x or j != y or include_self:
                    border_set.add((i, j))
        return border_set


if __name__ == '__main__':
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (0, 0)
    pygame.init()
    main()
