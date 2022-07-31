import enum
import itertools
import pygame
import random
import os
import sys
import time
import yaml


CONFIG = yaml.load(open('config.yaml'))
DIFFICULTIES = CONFIG['difficulties']
MUSIC = CONFIG['music']
KEY_BINDINGS = CONFIG['key_bindings']
MOUSE_BINDINGS = CONFIG['mouse_bindings']
TILESET = CONFIG['tileset']


def main():
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
        view.redraw() # for clock update
        if solver_enabled:
            solver = MinesweeperSolver(view.minesweeper)
            soln = solver.solve_one()
            if soln is not None:
                if soln['action'] == 'flag':
                    for coord in soln['coords']:
                        view.minesweeper.toggle_flag(*coord)
                elif soln['action'] == 'reveal':
                    for coord in soln['coords']:
                        view.minesweeper.reveal(*coord)


class MinesweeperView(object):

    def __init__(self, difficulty='easy', tileset='small'):
        self._set_difficulty(difficulty, init=True)
        self._set_tileset(tileset, init=True)
        self.start_new_game()

    def start_new_game(self):
        self.minesweeper = Minesweeper(**DIFFICULTIES[self.difficulty])
        self.start_time = None
        self.end_time = None
        self.redraw()

    def redraw(self):
        if self.screen is None:
            self._init_screen()
        black = 0, 0, 0
        white = 255, 255, 255
        self.screen.fill(black)
        tile_px = TILESET[self.tileset]['tile_px']
        for i in range(self.minesweeper.width):
            for j in range(self.minesweeper.height):
                rect = (tile_px * i, tile_px * j)
                square = self.minesweeper._squares[i, j]
                if square.flagged:
                    if self.minesweeper.state in MinesweeperState.end_states() and not square.is_mine:
                        tile_name = 'mine_hit'
                    else:
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

        font_px = TILESET[self.tileset]['font_px']
        font = pygame.font.SysFont('Consolas', font_px, bold=1)
        flag_remaining = font.render(str(self.minesweeper.flag_remaining), 1, white)
        self.screen.blit(
            self.tiles['flag'], (0.5 * tile_px, (self.minesweeper.height + 0.5) * tile_px))
        self.screen.blit(
            flag_remaining, (1.8 * tile_px, (self.minesweeper.height + 1) * tile_px - font_px / 2))
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
            self.tiles['clock'], ((self.minesweeper.width - 3) * tile_px, (self.minesweeper.height + 0.5) * tile_px))
        self.screen.blit(
            time_elapsed, ((self.minesweeper.width - 1.7) * tile_px, (self.minesweeper.height + 1) * tile_px - font_px / 2))

        if self.minesweeper.state is MinesweeperState.game_won:
            face_tile = self.tiles['win']
        elif self.minesweeper.state is MinesweeperState.game_lost:
            face_tile = self.tiles['lose']
        else:
            face_tile = self.tiles['normal']
        self.screen.blit(
            face_tile, ((self.minesweeper.width - 1) * tile_px / 2, (
                self.minesweeper.height + 0.5) * tile_px))

        pygame.display.flip()

    def handle_click(self, event):
        mouse_x, mouse_y = event.pos
        tile_px = TILESET[self.tileset]['tile_px']
        i = int(mouse_x / tile_px)
        j = int(mouse_y / tile_px)
        if i >= self.minesweeper.width or j >= self.minesweeper.height:
            return
        if event.button == MOUSE_BINDINGS['reveal']:
            if self.minesweeper.state is MinesweeperState.pregame:
                self.start_time = time.time()
            self.minesweeper.reveal(i, j)
        elif event.button == MOUSE_BINDINGS['burst_reveal']:
            self.minesweeper.burst_reveal(i, j)
        elif event.button == MOUSE_BINDINGS['flag']:
            self.minesweeper.toggle_flag(i, j)
        self.redraw()

    def handle_keyup(self, event):
        if event.key == getattr(pygame, KEY_BINDINGS['new_game']):
            self.start_new_game()
        elif event.key == getattr(pygame, KEY_BINDINGS['difficulty_1']):
            if self._set_difficulty('easy'):
                self.start_new_game()
        elif event.key == getattr(pygame, KEY_BINDINGS['difficulty_2']):
            if self._set_difficulty('medium'):
                self.start_new_game()
        elif event.key == getattr(pygame, KEY_BINDINGS['difficulty_3']):
            if self._set_difficulty('hard'):
                self.start_new_game()
        elif event.key == getattr(pygame, KEY_BINDINGS['difficulty_4']):
            if self._set_difficulty('ultimate'):
                self.start_new_game()
        elif event.key == getattr(pygame, KEY_BINDINGS['small_tiles']):
            self._set_tileset('small')
            self.redraw()
        elif event.key == getattr(pygame, KEY_BINDINGS['large_tiles']):
            self._set_tileset('large')
            self.redraw()
        elif event.key == getattr(pygame, KEY_BINDINGS['click_swap']):
            MOUSE_BINDINGS['reveal'], MOUSE_BINDINGS['flag'] = (
                MOUSE_BINDINGS['flag'], MOUSE_BINDINGS['reveal'])
        elif event.key == getattr(pygame, KEY_BINDINGS['print_console']):
            print(self.minesweeper)
        elif event.key == getattr(pygame, KEY_BINDINGS['help']):
            solver = MinesweeperSolver(self.minesweeper)
            soln = solver.solve_one()
            if soln is not None:
                if soln['action'] == 'flag':
                    self.minesweeper.toggle_flag(*next(iter(soln['coords'])))
                elif soln['action'] == 'reveal':
                    self.minesweeper.reveal(*next(iter(soln['coords'])))


    def _set_difficulty(self, difficulty, init=False):
        if not init and difficulty == self.difficulty:
            return False
        self.difficulty = difficulty
        self.screen = None
        pygame.display.set_caption(
            'Minesweeper [{}]'.format(self.difficulty))
        return True

    def _set_tileset(self, tileset, init=False):
        if not init and tileset == self.tileset:
            return
        self.tileset = tileset
        dir = TILESET[self.tileset]['dir']
        self.tiles = dict()
        for file in os.listdir(dir):
            if file.endswith('.png'):
                name = file[:-4]
                self.tiles[name] = pygame.image.load(os.path.join(dir, file))
        self.screen = None

    def _init_screen(self):
        tile_px = TILESET[self.tileset]['tile_px']
        size = (
            tile_px * DIFFICULTIES[self.difficulty]['width'],
            tile_px * (DIFFICULTIES[self.difficulty]['height'] + 2))
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


class MinesweeperSolver(object):

    def __init__(self, minesweeper):
        self.minesweeper = minesweeper

    def _add_leasts(self, at_least, coords, mines):
        if mines < 2 or len(coords) == mines or len(coords) < 3:
            return

        for sub_coords in itertools.combinations(coords, len(coords) - 1):
            at_least[frozenset(sub_coords)] = mines - 1
            self._add_leasts(at_least, sub_coords, mines - 1)

    def solve_one(self):
        m = dict()
        m[frozenset()] = 0
        for coord, square in self.minesweeper._squares.items():
            if square.revealed and square.bordering > 0:
                border_coords = self.minesweeper._get_bordering(*coord)
                unrevealed = set()
                flagged = set()
                for border_coord in border_coords:
                    border_square = self.minesweeper._squares[border_coord]
                    if border_square.revealed:
                        pass
                    elif border_square.flagged:
                        flagged.add(border_coord)
                    else:
                        unrevealed.add(border_coord)
                if len(unrevealed) > 0:
                    mines_unflagged = square.bordering - len(flagged)
                    m[frozenset(unrevealed)] = mines_unflagged

        at_least = dict()
        at_least_free = dict()
        for coords, mines in m.items():
            self._add_leasts(at_least, coords, mines)
            self._add_leasts(at_least_free, coords, len(coords) - mines)

        prev_size = None
        iters = 0
        while len(m) + len(at_least) + len(at_least_free) != prev_size:
            iters += 1
            prev_size = len(m) + len(at_least) + len(at_least_free)
            to_add = dict()
            for coords1, mines1 in m.items():
                for coords2, mines2 in m.items():
                    if coords1 is not coords2:
                        if coords1.issuperset(coords2):
                            diff_coords = coords1 - coords2
                            diff_mines = mines1 - mines2
                            if diff_coords:
                                if len(diff_coords) == diff_mines:
                                    if iters > 1:
                                        print('found iter {}'.format(iters))
                                    return {'action': 'flag',
                                            'coords': diff_coords}
                                if diff_mines == 0:
                                    if iters > 1:
                                        print('found iter {}'.format(iters))
                                    return {'action': 'reveal',
                                            'coords': diff_coords}
                                if diff_coords not in m:
                                    to_add[frozenset(diff_coords)] = diff_mines
                        if coords2.issuperset(coords1):
                            diff_coords = coords2 - coords1
                            diff_mines = mines2 - mines1
                            if diff_coords:
                                if len(diff_coords) == diff_mines:
                                    if iters > 1:
                                        print('found iter {}'.format(iters))
                                    return {'action': 'flag',
                                            'coords': diff_coords}
                                if diff_mines == 0:
                                    if iters > 1:
                                        print('found iter {}'.format(iters))
                                    return {'action': 'reveal',
                                            'coords': diff_coords}
                                if diff_coords not in m:
                                    to_add[frozenset(diff_coords)] = diff_mines
                for coords2, mines2 in at_least.items():
                    if coords1.issuperset(coords2):
                        diff_coords = coords1 - coords2
                        diff_mines = mines1 - mines2
                        if diff_coords:
                            if diff_mines == 0:
                                print('found LEASTS {}'.format(iters))
                                return {'action': 'reveal',
                                        'coords': diff_coords}
                            elif diff_mines != len(diff_coords):
                                self._add_leasts(at_least_free, diff_coords, len(diff_coords) - diff_mines)
                free1 = len(coords1) - mines1
                for coords2, free2 in at_least_free.items():
                    if coords1.issuperset(coords2):
                        diff_coords = coords1 - coords2
                        diff_free = free1 - free2
                        if diff_coords:
                            if diff_free == 0:
                                print('found LEASTS FREE {}'.format(iters))
                                return {'action': 'flag',
                                        'coords': diff_coords}
                            elif diff_free != len(diff_coords):
                                self._add_leasts(at_least, diff_coords, len(diff_coords) - diff_free)
            for i, j in to_add.items():
                m[i] = j
            # for coords, mines in m.items():
            #     self._add_leasts(at_least, coords, mines)
            #     self._add_leasts(at_least_free, coords, len(coords) - mines)


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
        pygame.mixer.music.stop()

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
            if MUSIC['enabled']:
                pygame.mixer.music.load(MUSIC['in_game'])
                pygame.mixer.music.play(-1)
        square = self._squares[x, y]
        if square.revealed or square.flagged:
            return
        square.revealed = True
        if square.is_mine:
            square.hit = True
            self.state = MinesweeperState.game_lost
            if MUSIC['enabled']:
                pygame.mixer.music.load(MUSIC['gameover'])
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
            if MUSIC['enabled']:
                pygame.mixer.music.load(MUSIC['victory'])
                pygame.mixer.music.play()

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
    #os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (0, 0)
    pygame.init()
    main()
