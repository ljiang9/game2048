#!/usr/bin/env python3
"""game2048 - 终端里的 2048 小游戏。

玩法：WASD 或 HJKL 移动方块，相同数字相撞合并，得分累加。
首次拼出 2048 即获胜（可继续挑战更高分）；棋盘填满且无法移动则游戏结束。

纯 Python 标准库，零依赖。
"""
import argparse
import random
import sys

VERSION = "0.1.0"

SIZE = 4          # 棋盘边长
WIN_TILE = 2048   # 获胜阈值
SPAWN_FOUR_CHANCE = 0.1  # 新方块为 4 的概率

# 方向键：WASD + HJKL 双别名（方向键需要终端 raw 模式，纯 stdlib
# 的 input() 行读取不支持，故只用字母键）
KEYS = {
    "w": "up", "k": "up",
    "s": "down", "j": "down",
    "a": "left", "h": "left",
    "d": "right", "l": "right",
}

DIRECTIONS = ("up", "left", "down", "right")

# 方块配色（ANSI 背景色，值越大颜色越深）
TILE_COLORS = {
    2: 47, 4: 43, 8: 103, 16: 102, 32: 46, 64: 42,
    128: 106, 256: 104, 512: 105, 1024: 45, 2048: 41,
}


# ---------- 核心逻辑（纯函数，方便单元测试） ----------

def move_row_left(row):
    """把一行向左移动并合并。返回 (新行, 本次合并得分)。

    规则：先压缩（去零），然后相邻相同两两合并，且每个方块每步
    只合并一次——[2,2,2,2] → [4,4,0,0]，不会变成 [8,0,0,0]。
    """
    cells = [v for v in row if v]
    merged_row = []
    gained = 0
    i = 0
    while i < len(cells):
        if i + 1 < len(cells) and cells[i] == cells[i + 1]:
            v = cells[i] * 2
            merged_row.append(v)
            gained += v
            i += 2  # 跳过被合并的那个，保证单次合并
        else:
            merged_row.append(cells[i])
            i += 1
    merged_row += [0] * (len(row) - len(merged_row))
    return merged_row, gained


def _transpose(board):
    return [list(r) for r in zip(*board)]


def _reverse_rows(board):
    return [list(reversed(r)) for r in board]


def move_board(board, direction):
    """按方向移动整个棋盘。返回 (新棋盘, 得分, 是否发生变化)。

    四个方向都归约到 move_row_left：right=反转行，up=转置，
    down=转置+反转行。
    """
    if direction == "left":
        work = board
    elif direction == "right":
        work = _reverse_rows(board)
    elif direction == "up":
        work = _transpose(board)
    elif direction == "down":
        work = _reverse_rows(_transpose(board))
    else:
        raise ValueError(f"未知方向：{direction}")

    new_rows, total = [], 0
    for row in work:
        r, g = move_row_left(row)
        new_rows.append(r)
        total += g

    if direction == "left":
        new_board = new_rows
    elif direction == "right":
        new_board = _reverse_rows(new_rows)
    elif direction == "up":
        new_board = _transpose(new_rows)
    else:
        new_board = _transpose(_reverse_rows(new_rows))

    moved = new_board != board
    return new_board, total, moved


def empty_cells(board):
    return [(r, c) for r in range(SIZE) for c in range(SIZE) if board[r][c] == 0]


def spawn_tile(board, rng):
    """在随机空格生成一个新方块：90% 是 2，10% 是 4。无空格则不做事。"""
    cells = empty_cells(board)
    if not cells:
        return False
    r, c = rng.choice(cells)
    board[r][c] = 4 if rng.random() < SPAWN_FOUR_CHANCE else 2
    return True


def can_move(board):
    """还有空格，或任意相邻（横/竖）两个相同数字，就能继续。"""
    if empty_cells(board):
        return True
    for r in range(SIZE):
        for c in range(SIZE):
            v = board[r][c]
            if c + 1 < SIZE and board[r][c + 1] == v:
                return True
            if r + 1 < SIZE and board[r + 1][c] == v:
                return True
    return False


def max_tile(board):
    return max(v for row in board for v in row)


def new_board():
    return [[0] * SIZE for _ in range(SIZE)]


# ---------- 渲染 ----------

def _tile_text(v):
    if v == 0:
        return "    "
    return f"{v:>4}"


def render(board, score, use_color=True):
    """把棋盘画成等宽方格。"""
    bar = "+" + "+".join(["-----"] * SIZE) + "+"
    lines = [bar]
    for row in board:
        cells = []
        for v in row:
            text = f" {_tile_text(v)} "
            if use_color and v in TILE_COLORS:
                text = f"\033[{TILE_COLORS[v]};30m{text}\033[0m"
            elif use_color and v > 2048:
                text = f"\033[101;30m{text}\033[0m"
            cells.append(text)
        lines.append("|" + "|".join(cells) + "|")
        lines.append(bar)
    lines.append(f"得分：{score}")
    return "\n".join(lines)


# ---------- 游戏流程 ----------

class Game:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.board = new_board()
        self.score = 0
        self.moves = 0
        self.won = False  # 是否已经弹出过获胜提示
        spawn_tile(self.board, self.rng)
        spawn_tile(self.board, self.rng)

    def step(self, direction):
        """走一步。返回 True 表示棋盘发生变化（并已生成新方块）。"""
        new_board_state, gained, moved = move_board(self.board, direction)
        if not moved:
            return False
        self.board = new_board_state
        self.score += gained
        self.moves += 1
        spawn_tile(self.board, self.rng)
        return True

    def over(self):
        return not can_move(self.board)

    def check_win(self):
        if not self.won and max_tile(self.board) >= WIN_TILE:
            self.won = True
            return True
        return False


def play_interactive():
    game = Game()
    use_color = sys.stdout.isatty()
    print("=== 2048 ===")
    print("操作：W 上 / S 下 / A 左 / D 右（也可用 H J K L），Q 退出")
    print("目标：拼出 2048！相同数字相撞合并。\n")
    while True:
        print(render(game.board, game.score, use_color=use_color))
        if game.check_win():
            print(f"\n🎉 恭喜！你拼出了 {WIN_TILE}！可以继续挑战更高分。\n")
        if game.over():
            print(f"\n游戏结束！共走 {game.moves} 步，最终得分 {game.score}，"
                  f"最大方块 {max_tile(game.board)}。")
            return 0
        try:
            key = input("移动 (WASD/HJKL, Q退出)：").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n已退出。得分 {game.score}，走了 {game.moves} 步。")
            return 0
        if not key:
            continue
        if key in ("q", "quit", "exit"):
            print(f"已退出。得分 {game.score}，走了 {game.moves} 步。")
            return 0
        direction = KEYS.get(key[0])
        if direction is None:
            print("无效按键，请用 W/A/S/D 或 H/J/K/L。")
            continue
        if not game.step(direction):
            print("这个方向动不了，换个方向试试。")


def play_auto(count, seed):
    """脚本化随机游走：用于验证逻辑和跑统计。固定 seed 可复现。"""
    rng = random.Random(seed)
    game = Game(rng=rng)
    done = 0
    for _ in range(count):
        dirs = list(DIRECTIONS)
        rng.shuffle(dirs)
        moved = False
        for d in dirs:
            if game.step(d):
                moved = True
                break
        if not moved:  # 无路可走，游戏结束
            break
        done += 1
        if game.check_win():
            pass
    print(f"自动游走完成：走了 {done} 步，得分 {game.score}，"
          f"最大方块 {max_tile(game.board)}，"
          f"{'拼出2048🎉' if game.won else '未拼出2048'}，"
          f"{'棋盘已死' if game.over() else '仍可继续'}")
    print(render(game.board, game.score, use_color=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="game2048",
        description="终端 2048 小游戏：WASD/HJKL 移动，合并相同数字，拼出 2048。",
    )
    parser.add_argument("--auto", type=int, metavar="N", default=0,
                        help="自动随机走 N 步（验证/统计用），不进入交互模式")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子，配合 --auto 可复现同一局")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args(argv)

    if args.auto and args.auto > 0:
        return play_auto(args.auto, args.seed)
    if not sys.stdin.isatty():
        print("错误：交互模式需要终端（stdin 不是 tty）。"
              "非交互环境请用 --auto N。", file=sys.stderr)
        return 2
    return play_interactive()


if __name__ == "__main__":
    sys.exit(main())
