"""Unit tests for minesweeper.py"""

import unittest
from minesweeper import create_board, flood_fill, parse_input, chord_reveal


class TestCreateBoard(unittest.TestCase):
    def test_board_dimensions(self):
        board, mines = create_board(9, 9, 10)
        self.assertEqual(len(board), 9)
        self.assertEqual(len(board[0]), 9)

    def test_mine_count(self):
        board, mines = create_board(9, 9, 10)
        self.assertEqual(len(mines), 10)
        count = sum(1 for r in range(9) for c in range(9) if board[r][c] == -1)
        self.assertEqual(count, 10)

    def test_neighbor_counts(self):
        """Every non-mine cell value should equal the number of mine neighbours."""
        rows, cols, num_mines = 9, 9, 10
        board, mines = create_board(rows, cols, num_mines)
        for r in range(rows):
            for c in range(cols):
                if board[r][c] == -1:
                    continue
                expected = sum(
                    1
                    for dr in [-1, 0, 1]
                    for dc in [-1, 0, 1]
                    if 0 <= r + dr < rows
                    and 0 <= c + dc < cols
                    and board[r + dr][c + dc] == -1
                )
                self.assertEqual(board[r][c], expected)

    def test_zero_mines_board(self):
        board, mines = create_board(5, 5, 0)
        self.assertEqual(len(mines), 0)
        for r in range(5):
            for c in range(5):
                self.assertEqual(board[r][c], 0)


class TestFloodFill(unittest.TestCase):
    def _simple_board(self):
        """
        A 3x3 board with no mines – all zeros.
        flood_fill from (0,0) should reveal all 9 cells.
        """
        board = [[0] * 3 for _ in range(3)]
        return board

    def test_flood_fill_all_zeros(self):
        board = self._simple_board()
        revealed = set()
        flood_fill(board, revealed, 3, 3, 0, 0)
        self.assertEqual(len(revealed), 9)

    def test_flood_fill_stops_at_numbers(self):
        """
        Board:
          0 0 1
          0 0 1
          0 0 1
        flood_fill from (0,0) should reveal all cells (numbers don't block spreading,
        but the spread starts from 0-cells and includes numbered neighbours).
        """
        board = [
            [0, 0, 1],
            [0, 0, 1],
            [0, 0, 1],
        ]
        revealed = set()
        flood_fill(board, revealed, 3, 3, 0, 0)
        # All non-mine cells should be revealed because zeros expand and pull in neighbours
        self.assertEqual(len(revealed), 9)

    def test_flood_fill_single_number_cell(self):
        """Starting flood_fill on a numbered cell reveals only that cell."""
        board = [
            [1, 1, 1],
            [1, -1, 1],
            [1, 1, 1],
        ]
        revealed = set()
        flood_fill(board, revealed, 3, 3, 0, 0)
        self.assertIn((0, 0), revealed)
        # Because (0,0) is '1' (not 0), flood should not expand further
        self.assertEqual(len(revealed), 1)


class TestParseInput(unittest.TestCase):
    def test_open_two_parts(self):
        self.assertEqual(parse_input("3 4", 9, 9), ("open", 3, 4))

    def test_flag_action(self):
        self.assertEqual(parse_input("flag 2 5", 9, 9), ("flag", 2, 5))

    def test_unflag_action(self):
        self.assertEqual(parse_input("unflag 0 0", 9, 9), ("unflag", 0, 0))

    def test_out_of_bounds(self):
        self.assertIsNone(parse_input("9 9", 9, 9))  # indices 0-8 only
        self.assertIsNone(parse_input("0 9", 9, 9))

    def test_invalid_action(self):
        self.assertIsNone(parse_input("boom 1 1", 9, 9))

    def test_non_numeric(self):
        self.assertIsNone(parse_input("a b", 9, 9))

    def test_too_few_parts(self):
        self.assertIsNone(parse_input("3", 9, 9))

    def test_too_many_parts(self):
        self.assertIsNone(parse_input("open 1 2 3", 9, 9))

    def test_boundary_values(self):
        self.assertEqual(parse_input("0 0", 9, 9), ("open", 0, 0))
        self.assertEqual(parse_input("8 8", 9, 9), ("open", 8, 8))


class TestChordReveal(unittest.TestCase):
    def _make_board(self):
        """
        3x3 board:
          -1  1  0
           1  1  0
           0  0  0
        Mine at (0,0). Cell (0,1) has value 1.
        """
        board = [
            [-1, 1, 0],
            [1,  1, 0],
            [0,  0, 0],
        ]
        mines = {(0, 0)}
        return board, mines

    def test_not_triggered_on_unrevealed(self):
        board, _ = self._make_board()
        revealed = set()
        flagged = set()
        triggered, hit = chord_reveal(board, revealed, flagged, 3, 3, 0, 1)
        self.assertFalse(triggered)
        self.assertFalse(hit)

    def test_not_triggered_insufficient_flags(self):
        board, _ = self._make_board()
        revealed = {(0, 1)}
        flagged = set()   # need 1 flag around (0,1) but have none
        triggered, hit = chord_reveal(board, revealed, flagged, 3, 3, 0, 1)
        self.assertFalse(triggered)

    def test_triggered_safe(self):
        """Flag the mine; chord should reveal remaining neighbors safely."""
        board, _ = self._make_board()
        revealed = {(0, 1)}
        flagged = {(0, 0)}  # correct mine flagged
        triggered, hit = chord_reveal(board, revealed, flagged, 3, 3, 0, 1)
        self.assertTrue(triggered)
        self.assertFalse(hit)
        # (1,0), (1,1), (1,2), (0,2) should have been revealed (flood from zeros too)
        self.assertIn((1, 0), revealed)
        self.assertIn((1, 1), revealed)

    def test_triggered_hits_mine(self):
        """Flag the wrong cell; chord should expose the actual mine."""
        board, _ = self._make_board()
        revealed = {(0, 1)}
        flagged = {(0, 2)}  # wrong flag – (0,0) is the mine
        triggered, hit = chord_reveal(board, revealed, flagged, 3, 3, 0, 1)
        self.assertTrue(triggered)
        self.assertTrue(hit)
        self.assertIn((0, 0), revealed)  # mine cell added to revealed

    def test_not_triggered_on_zero_cell(self):
        board, _ = self._make_board()
        revealed = {(1, 2)}   # value 0 cell
        flagged = set()
        triggered, hit = chord_reveal(board, revealed, flagged, 3, 3, 1, 2)
        self.assertFalse(triggered)


if __name__ == "__main__":
    unittest.main()
