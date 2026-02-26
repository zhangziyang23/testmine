"""
扫雷 (Minesweeper) - 图形界面版本
用法: python minesweeper.py
操作: 左键单击打开格子，右键单击标记/取消标记地雷
"""

import random
import json
import os

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    _HAS_TK = True
except ImportError:
    _HAS_TK = False


# ---------------------------------------------------------------------------
# 核心游戏逻辑（与界面无关，便于单元测试）
# ---------------------------------------------------------------------------

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


def chord_reveal(board, revealed, flagged, rows, cols, r, c):
    """和弦操作：在已揭开的数字格子上，若周围旗帜数等于格子数字，自动揭开周围未标记未揭开的格子.

    返回 (triggered, hit_mine)：
      triggered  - 条件满足并执行了操作
      hit_mine   - 操作过程中踩到了地雷
    """
    if (r, c) not in revealed or board[r][c] <= 0:
        return False, False

    flag_count = 0
    unopened = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if (nr, nc) in flagged:
                    flag_count += 1
                elif (nr, nc) not in revealed:
                    unopened.append((nr, nc))

    if flag_count != board[r][c]:
        return False, False

    hit_mine = False
    for nr, nc in unopened:
        if board[nr][nc] == -1:
            hit_mine = True
            revealed.add((nr, nc))
        else:
            flood_fill(board, revealed, rows, cols, nr, nc)

    return True, hit_mine


def is_solvable(board, mines, rows, cols, start_r, start_c):
    """Return True if the board can be fully solved from (start_r, start_c) without guessing.

    Uses constraint propagation:
      - If unrevealed neighbours of a cell equal its remaining mine count, all are mines.
      - If a cell's mine count is already satisfied by flags, all other neighbours are safe.
    """
    revealed = set()
    flagged = set()

    flood_fill(board, revealed, rows, cols, start_r, start_c)

    changed = True
    while changed:
        changed = False
        for r in range(rows):
            for c in range(cols):
                if (r, c) not in revealed or board[r][c] <= 0:
                    continue

                unrevealed = []
                flagged_count = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if (nr, nc) in flagged:
                                flagged_count += 1
                            elif (nr, nc) not in revealed:
                                unrevealed.append((nr, nc))

                remaining = board[r][c] - flagged_count
                if remaining == len(unrevealed) and remaining > 0:
                    for pos in unrevealed:
                        flagged.add(pos)
                    changed = True
                elif remaining == 0 and unrevealed:
                    for pos in unrevealed:
                        flood_fill(board, revealed, rows, cols, pos[0], pos[1])
                    changed = True

    safe_cells = rows * cols - len(mines)
    return len(revealed) == safe_cells


def parse_input(user_input, rows, cols):
    """解析玩家输入，返回 (action, row, col) 或 None.（保留供单元测试使用）"""
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


# ---------------------------------------------------------------------------
# 图形界面
# ---------------------------------------------------------------------------

CELL_SIZE = 32  # 每个格子的默认像素大小
_TOP_FRAME_HEIGHT = 54  # 顶部信息栏高度估算（像素）

# 数字颜色
NUMBER_COLORS = {
    1: "#0000ff",
    2: "#008000",
    3: "#ff0000",
    4: "#000080",
    5: "#800000",
    6: "#008080",
    7: "#000000",
    8: "#808080",
}


class MinesweeperGUI:
    def __init__(self, root, rows, cols, num_mines):
        self.root = root
        self.rows = rows
        self.cols = cols
        self.num_mines = num_mines

        self.board = None
        self.mines = None
        self.revealed = set()
        self.flagged = set()
        self.questioned = set()
        self.first_move = True
        self.game_over = False
        self._cell_size = CELL_SIZE  # 当前格子像素大小，随窗口缩放

        # 每种难度的最佳成绩（秒），key 为 (rows, cols, num_mines)
        self._best_times = self._load_best_times()

        self._build_ui()
        self._new_game()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.root.title("扫雷")
        self.root.resizable(True, True)
        self.root.minsize(self.cols * 8 + 4, self.rows * 8 + _TOP_FRAME_HEIGHT)

        # 顶部信息栏
        self._top_frame = tk.Frame(self.root, bg="#c0c0c0", pady=4)
        self._top_frame.pack(fill=tk.X)

        self.mine_label = tk.Label(
            self._top_frame, text="💣 000", font=("Courier", 14, "bold"),
            bg="#c0c0c0", fg="#cc0000", width=7, anchor="w"
        )
        self.mine_label.pack(side=tk.LEFT, padx=8)

        self.reset_btn = tk.Button(
            self._top_frame, text="🙂", font=("Arial", 14),
            command=self._new_game, relief=tk.RAISED, bd=2,
            bg="#c0c0c0", activebackground="#a0a0a0"
        )
        self.reset_btn.pack(side=tk.LEFT, expand=True)

        self.time_label = tk.Label(
            self._top_frame, text="⏱ 000", font=("Courier", 14, "bold"),
            bg="#c0c0c0", fg="#cc0000", width=7, anchor="e"
        )
        self.time_label.pack(side=tk.RIGHT, padx=8)

        # 棋盘画布（随窗口伸缩）
        canvas_width = self.cols * CELL_SIZE
        canvas_height = self.rows * CELL_SIZE
        self.canvas = tk.Canvas(
            self.root, width=canvas_width, height=canvas_height,
            bg="#c0c0c0", bd=2, relief=tk.SUNKEN
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 鼠标绑定：左键打开，右键标记
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # 菜单
        menubar = tk.Menu(self.root)
        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(label="初级 (9×9, 10 雷)", command=lambda: self._change_difficulty(9, 9, 10))
        game_menu.add_command(label="中级 (16×16, 40 雷)", command=lambda: self._change_difficulty(16, 16, 40))
        game_menu.add_command(label="高级 (16×30, 99 雷)", command=lambda: self._change_difficulty(16, 30, 99))
        game_menu.add_separator()
        game_menu.add_command(label="自定义…", command=self._custom_difficulty)
        game_menu.add_separator()
        game_menu.add_command(label="查看最佳成绩", command=self._show_best_times)
        game_menu.add_separator()
        game_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="游戏", menu=game_menu)
        self.root.config(menu=menubar)

        self._elapsed = 0
        self._timer_id = None

    # ------------------------------------------------------------------
    # 游戏控制
    # ------------------------------------------------------------------

    def _new_game(self):
        """重置并开始新游戏."""
        self._stop_timer()
        self.board, self.mines = create_board(self.rows, self.cols, self.num_mines)
        self.revealed = set()
        self.flagged = set()
        self.questioned = set()
        self.first_move = True
        self.game_over = False
        self._elapsed = 0
        self.reset_btn.config(text="🙂")
        self._update_mine_label()
        self._update_time_label()
        self._draw_board()

    def _change_difficulty(self, rows, cols, num_mines):
        self.rows = rows
        self.cols = cols
        self.num_mines = num_mines
        self._cell_size = CELL_SIZE
        # 调整窗口大小以适应新难度
        top_h = self._top_frame.winfo_height()
        if top_h < 10:
            top_h = _TOP_FRAME_HEIGHT  # 顶部信息栏高度估算
        self.root.geometry(f"{cols * CELL_SIZE}x{rows * CELL_SIZE + top_h}")
        self.root.minsize(cols * 8 + 4, rows * 8 + top_h)
        self._new_game()

    def _custom_difficulty(self):
        rows = simpledialog.askinteger("自定义", "行数 (5-30):", minvalue=5, maxvalue=30, parent=self.root)
        if rows is None:
            return
        cols = simpledialog.askinteger("自定义", "列数 (5-30):", minvalue=5, maxvalue=30, parent=self.root)
        if cols is None:
            return
        max_mines = rows * cols - 1
        num_mines = simpledialog.askinteger(
            "自定义", f"地雷数 (1-{max_mines}):", minvalue=1, maxvalue=max_mines, parent=self.root
        )
        if num_mines is None:
            return
        self._change_difficulty(rows, cols, num_mines)

    # ------------------------------------------------------------------
    # 鼠标事件
    # ------------------------------------------------------------------

    def _cell_from_event(self, event):
        """将鼠标坐标转换为 (row, col)."""
        c = event.x // self._cell_size
        r = event.y // self._cell_size
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return r, c
        return None, None

    def _on_left_click(self, event):
        """左键单击：打开格子；在已揭开的数字格子上执行和弦操作."""
        if self.game_over:
            return
        r, c = self._cell_from_event(event)
        if r is None:
            return

        # 和弦操作：点击已揭开的数字格子
        if (r, c) in self.revealed and self.board[r][c] > 0:
            triggered, hit_mine = chord_reveal(
                self.board, self.revealed, self.flagged, self.rows, self.cols, r, c
            )
            if triggered:
                if hit_mine:
                    self.game_over = True
                    self._stop_timer()
                    self.reset_btn.config(text="😵")
                    self._draw_board(show_all=True)
                    messagebox.showinfo("游戏结束", "💥 踩到地雷！游戏结束！")
                    return
                self._check_win()
                self._draw_board()
            return

        if (r, c) in self.flagged or (r, c) in self.revealed:
            return

        # 第一次点击时保证不踩雷且棋盘可解，启动计时器
        if self.first_move:
            _MAX_REGEN = 100
            for _ in range(_MAX_REGEN):
                if self.board[r][c] != -1 and is_solvable(
                    self.board, self.mines, self.rows, self.cols, r, c
                ):
                    break
                self.board, self.mines = create_board(self.rows, self.cols, self.num_mines)
            else:
                # 回退：至少确保首次点击不踩雷
                while self.board[r][c] == -1:
                    self.board, self.mines = create_board(self.rows, self.cols, self.num_mines)
            self.first_move = False
            self._start_timer()

        if self.board[r][c] == -1:
            # 踩雷
            self.revealed.add((r, c))
            self.game_over = True
            self._stop_timer()
            self.reset_btn.config(text="😵")
            self._draw_board(show_all=True)
            messagebox.showinfo("游戏结束", "💥 踩到地雷！游戏结束！")
            return

        flood_fill(self.board, self.revealed, self.rows, self.cols, r, c)
        self._check_win()
        self._draw_board()

    def _on_right_click(self, event):
        """右键单击：循环切换标记状态（未标记 → 旗帜 → 疑问 → 未标记）."""
        if self.game_over:
            return
        r, c = self._cell_from_event(event)
        if r is None:
            return
        if (r, c) in self.revealed:
            return

        if (r, c) in self.flagged:
            self.flagged.discard((r, c))
            self.questioned.add((r, c))
        elif (r, c) in self.questioned:
            self.questioned.discard((r, c))
        else:
            self.flagged.add((r, c))

        self._update_mine_label()
        self._draw_board()

    def _on_canvas_resize(self, event):
        """画布大小改变时，重新计算格子像素大小并重绘棋盘."""
        if not self.cols or not self.rows:
            return
        new_size = min(event.width // self.cols, event.height // self.rows)
        new_size = max(new_size, 1)
        if new_size != self._cell_size:
            self._cell_size = new_size
            self._draw_board(show_all=self.game_over)

    # ------------------------------------------------------------------
    # 最佳成绩持久化
    # ------------------------------------------------------------------

    _SCORES_FILE = os.path.join(os.path.expanduser("~"), ".minesweeper_scores.json")

    def _load_best_times(self):
        """从文件加载最佳成绩，若文件不存在或损坏则返回空字典."""
        try:
            with open(self._SCORES_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # JSON keys are strings; convert "r,c,m" back to (r, c, m)
            return {tuple(int(x) for x in k.split(",")): v for k, v in raw.items()}
        except Exception:
            return {}

    def _save_best_times(self):
        """将最佳成绩保存到文件."""
        try:
            raw = {",".join(str(x) for x in k): v for k, v in self._best_times.items()}
            with open(self._SCORES_FILE, "w", encoding="utf-8") as f:
                json.dump(raw, f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 胜利检测 & 最佳成绩
    # ------------------------------------------------------------------

    def _check_win(self):
        """若所有安全格子已揭开则判定胜利."""
        safe_cells = self.rows * self.cols - self.num_mines
        if len(self.revealed) == safe_cells:
            self.game_over = True
            self._stop_timer()
            self.reset_btn.config(text="😎")
            self._draw_board(show_all=True)
            key = (self.rows, self.cols, self.num_mines)
            prev = self._best_times.get(key)
            if prev is None or self._elapsed < prev:
                self._best_times[key] = self._elapsed
                self._save_best_times()
                msg = f"🎉 恭喜你，获胜了！\n用时：{self._elapsed} 秒\n🏆 新纪录！"
            else:
                msg = f"🎉 恭喜你，获胜了！\n用时：{self._elapsed} 秒\n最佳成绩：{prev} 秒"
            messagebox.showinfo("恭喜", msg)

    def _show_best_times(self):
        """显示各难度的最佳成绩."""
        LEVELS = {
            (9, 9, 10): "初级 (9×9, 10 雷)",
            (16, 16, 40): "中级 (16×16, 40 雷)",
            (16, 30, 99): "高级 (16×30, 99 雷)",
        }
        lines = []
        for key, name in LEVELS.items():
            t = self._best_times.get(key)
            lines.append(f"{name}：{'--' if t is None else f'{t} 秒'}")
        messagebox.showinfo("最佳成绩", "\n".join(lines))

    # ------------------------------------------------------------------
    # 计时器
    # ------------------------------------------------------------------

    def _start_timer(self):
        self._tick()

    def _tick(self):
        self._elapsed += 1
        self._update_time_label()
        self._timer_id = self.root.after(1000, self._tick)

    def _stop_timer(self):
        if self._timer_id is not None:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def _draw_board(self, show_all=False):
        self.canvas.delete("all")
        for r in range(self.rows):
            for c in range(self.cols):
                self._draw_cell(r, c, show_all)

    def _draw_cell(self, r, c, show_all=False):
        cs = self._cell_size
        x0 = c * cs
        y0 = r * cs
        x1 = x0 + cs
        y1 = y0 + cs
        cx = x0 + cs // 2
        cy = y0 + cs // 2
        fs = max(8, cs * 14 // 32)  # 字体大小随格子缩放

        if (r, c) in self.revealed or show_all:
            val = self.board[r][c]
            if val == -1:
                # 地雷
                bg = "#ff4444" if (r, c) in self.revealed else "#c0c0c0"
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=bg, outline="#999999")
                self.canvas.create_text(cx, cy, text="💣", font=("Arial", fs))
            elif val == 0:
                self.canvas.create_rectangle(x0, y0, x1, y1, fill="#d0d0d0", outline="#999999")
            else:
                self.canvas.create_rectangle(x0, y0, x1, y1, fill="#d0d0d0", outline="#999999")
                color = NUMBER_COLORS.get(val, "#000000")
                self.canvas.create_text(
                    cx, cy, text=str(val),
                    font=("Arial", max(8, cs * 13 // 32), "bold"), fill=color
                )
        elif (r, c) in self.flagged:
            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#c0c0c0", outline="#808080")
            # 立体边框
            self.canvas.create_line(x0, y1, x0, y0, x1, y0, fill="#ffffff", width=2)
            self.canvas.create_line(x1, y0, x1, y1, x0, y1, fill="#808080", width=2)
            self.canvas.create_text(cx, cy, text="🚩", font=("Arial", fs))
        elif (r, c) in self.questioned:
            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#c0c0c0", outline="#808080")
            self.canvas.create_line(x0, y1, x0, y0, x1, y0, fill="#ffffff", width=2)
            self.canvas.create_line(x1, y0, x1, y1, x0, y1, fill="#808080", width=2)
            self.canvas.create_text(cx, cy, text="❓", font=("Arial", fs))
        else:
            # 未揭开
            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#c0c0c0", outline="#808080")
            self.canvas.create_line(x0, y1, x0, y0, x1, y0, fill="#ffffff", width=2)
            self.canvas.create_line(x1, y0, x1, y1, x0, y1, fill="#808080", width=2)

    def _update_mine_label(self):
        remaining = self.num_mines - len(self.flagged)
        self.mine_label.config(text=f"💣 {remaining:03d}")

    def _update_time_label(self):
        self.time_label.config(text=f"⏱ {min(self._elapsed, 999):03d}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    if not _HAS_TK:
        print("错误：未找到 tkinter 模块，无法启动图形界面。")
        return
    root = tk.Tk()
    MinesweeperGUI(root, rows=9, cols=9, num_mines=10)
    root.mainloop()


if __name__ == "__main__":
    main()
