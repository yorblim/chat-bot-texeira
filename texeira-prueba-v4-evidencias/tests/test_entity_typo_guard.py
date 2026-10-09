"""Ambiguous or large spelling differences must not select a tour by guesswork."""
import unittest

from verified_routes import _unique_typo_entity


class EntityTypoGuard(unittest.TestCase):
    def test_single_transposition_and_deletion_preserve_unique_entity(self):
        aliases = {"inca": ["camino inca", "inca trail"], "jungle": ["inka jungle"]}
        self.assertEqual(_unique_typo_entity("q cuesta camnio inca", aliases), "inca")
        self.assertEqual(_unique_typo_entity("price of inca tral", aliases), "inca")

    def test_two_similar_destinations_remain_unassigned(self):
        aliases = {"a": ["camino inca"], "b": ["camino inka"]}
        # "inxa" differs in one position from both "inca" and "inka".
        self.assertIsNone(_unique_typo_entity("precio camino inxa", aliases))

    def test_distant_names_and_single_word_matches_do_not_bind(self):
        aliases = {"inca": ["camino inca"], "lake": ["humantay"]}
        self.assertIsNone(_unique_typo_entity("precio cmn incx", aliases))
        self.assertIsNone(_unique_typo_entity("precio humntay", aliases))

    def test_two_misspelled_tours_in_one_question_remain_ambiguous(self):
        aliases = {"inca": ["camino inca"], "jungle": ["inka jungle"]}
        self.assertIsNone(_unique_typo_entity("camnio inca o inka jungl", aliases))


if __name__ == "__main__":
    unittest.main(verbosity=2)
