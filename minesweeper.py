"""
扫雷 (Minesweeper) - 命令行版本
用法: python minesweeper.py
"""

import random
import sys


def create_board(rows, cols, num_mines):
    """创建并返回一个随机放置地雷的棋盘."""
    board = [[0] * cols for _ in range(rows)]

    # 随机放置地雷
    mines = set()
    while len(mines) < num_mines:
        r = random.randint(0, rows - 1)
        c = random.randint(0, cols - 1)
        mines.add((r, c))

    for r, c in mines:
        board[r][c] = -1  # -1 表示地雷

    # 计算每个非地雷格子周围的地雷数
    for r in range(rows):
        for c in range(cols):
            if board[r][c] == -1:
                continue
            count = 0
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and board[nr][nc] == -1:
                        count += 1
            board[r][c] = count

    return board, mines


def print_board(board, revealed, flagged, rows, cols, show_all=False):
    """打印当前棋盘状态."""
    col_header = "    " + "  ".join(f"{c:2d}" for c in range(cols))
    print(col_header)
    print("    " + "---" * cols)

    for r in range(rows):
        row_str = f"{r:2d} |"
        for c in range(cols):
            if show_all:
                val = board[r][c]
                if val == -1:
                    row_str += "  *"
                else:
                    row_str += f"  {val}" if val > 0 else "  ."
            elif (r, c) in flagged:
                row_str += "  F"
            elif (r, c) not in revealed:
                row_str += "  #"
            else:
                val = board[r][c]
                if val == -1:
                    row_str += "  *"
                elif val == 0:
                    row_str += "  ."
                else:
                    row_str += f"  {val}"
        print(row_str)


def flood_fill(board, revealed, rows, cols, r, c):
    """从空白格子开始自动展开周围的格子."""
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if (cr, cc) in revealed:
            continue
        revealed.add((cr, cc))
        if board[cr][cc] == 0:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in revealed:
                        stack.append((nr, nc))


def get_difficulty():
    """让玩家选择难度."""
    print("请选择难度:")
    print("  1. 初级 (9x9, 10 地雷)")
    print("  2. 中级 (16x16, 40 地雷)")
    print("  3. 高级 (16x30, 99 地雷)")
    print("  4. 自定义")

    while True:
        choice = input("输入选项 (1-4): ").strip()
        if choice == "1":
            return 9, 9, 10
        elif choice == "2":
            return 16, 16, 40
        elif choice == "3":
            return 16, 30, 99
        elif choice == "4":
            try:
                rows = int(input("行数 (5-30): "))
                cols = int(input("列数 (5-30): "))
                max_mines = rows * cols - 1
                mines = int(input(f"地雷数 (1-{max_mines}): "))
                if 5 <= rows <= 30 and 5 <= cols <= 30 and 1 <= mines <= max_mines:
                    return rows, cols, mines
                else:
                    print("输入超出范围，请重试。")
            except ValueError:
                print("无效输入，请输入数字。")
        else:
            print("无效选项，请重试。")


def parse_input(user_input, rows, cols):
    """解析玩家输入，返回 (action, row, col) 或 None."""
    parts = user_input.strip().split()
    if len(parts) == 2:
        action = "open"
        r_str, c_str = parts
    elif len(parts) == 3:
        action, r_str, c_str = parts
        action = action.lower()
        if action not in ("open", "flag", "unflag"):
            return None
    else:
        return None

    try:
        r, c = int(r_str), int(c_str)
    except ValueError:
        return None

    if not (0 <= r < rows and 0 <= c < cols):
        return None

    return action, r, c


def play_game(rows, cols, num_mines):
    """主游戏循环."""
    board, mines = create_board(rows, cols, num_mines)
    revealed = set()
    flagged = set()
    first_move = True

    print(f"\n棋盘: {rows}行 x {cols}列，{num_mines} 个地雷")
    print("操作: 输入 '行 列' 打开格子，'flag 行 列' 标记地雷，'unflag 行 列' 取消标记")
    print("      输入 'q' 退出\n")

    while True:
        print_board(board, revealed, flagged, rows, cols)
        remaining = num_mines - len(flagged)
        print(f"\n剩余地雷数: {remaining}  已揭开: {len(revealed)}/{rows * cols - num_mines}")

        user_input = input("\n请输入操作: ").strip()
        if user_input.lower() == "q":
            print("已退出游戏。")
            return

        result = parse_input(user_input, rows, cols)
        if result is None:
            print("无效输入，请重试。格式: '行 列' 或 'flag 行 列'")
            continue

        action, r, c = result

        if action == "open":
            if (r, c) in flagged:
                print("该格子已被标记，请先取消标记。")
                continue
            if (r, c) in revealed:
                print("该格子已经被揭开。")
                continue

            # 第一次点击保证不踩雷
            while first_move and board[r][c] == -1:
                board, mines = create_board(rows, cols, num_mines)
            first_move = False

            if board[r][c] == -1:
                # 踩雷，游戏结束
                revealed.add((r, c))
                print_board(board, revealed, flagged, rows, cols, show_all=True)
                print("\n💥 踩到地雷！游戏结束！")
                return

            flood_fill(board, revealed, rows, cols, r, c)

            # 检查胜利条件
            safe_cells = rows * cols - num_mines
            if len(revealed) == safe_cells:
                print_board(board, revealed, flagged, rows, cols, show_all=True)
                print("\n🎉 恭喜你，获胜了！")
                return

        elif action == "flag":
            if (r, c) in revealed:
                print("该格子已被揭开，无法标记。")
            else:
                flagged.add((r, c))
                print(f"已标记 ({r}, {c})")

        elif action == "unflag":
            if (r, c) in flagged:
                flagged.discard((r, c))
                print(f"已取消标记 ({r}, {c})")
            else:
                print("该格子未被标记。")


def main():
    print("=" * 40)
    print("       欢迎来到扫雷游戏！")
    print("=" * 40)

    while True:
        rows, cols, num_mines = get_difficulty()
        play_game(rows, cols, num_mines)

        again = input("\n是否再玩一局? (y/n): ").strip().lower()
        if again != "y":
            print("感谢游玩，再见！")
            break


if __name__ == "__main__":
    main()
