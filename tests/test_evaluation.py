import unittest

from newspaper_ner.evaluation import _join_physical_lines


class PhysicalLineJoiningTests(unittest.TestCase):
    def test_joins_a_printed_line_end_hyphen_only_when_enabled(self):
        lines = ["gone hunt-", "ing—not specially"]

        self.assertEqual(
            _join_physical_lines(lines, join_hyphens=False),
            "gone hunt- ing—not specially",
        )
        self.assertEqual(
            _join_physical_lines(lines, join_hyphens=True),
            "gone hunting—not specially",
        )

    def test_em_dash_at_line_start_is_joined_without_a_space(self):
        self.assertEqual(
            _join_physical_lines(["ducks", "—yesterday,"], join_hyphens=False),
            "ducks—yesterday,",
        )

    def test_em_dash_at_line_end_is_joined_without_a_space(self):
        self.assertEqual(
            _join_physical_lines(["November 9—", "(AP)—news"], join_hyphens=False),
            "November 9—(AP)—news",
        )


if __name__ == "__main__":
    unittest.main()
