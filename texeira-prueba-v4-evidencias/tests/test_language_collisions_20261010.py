"""Finite language-routing regressions; no model or transport quality claims.

Run with tests/run_isolated.py. Only the installed production language helper
is called. Inputs and expected languages are authored independently, including
French/Portuguese and Italian/Portuguese collisions and existing ES/EN/PT cues.
No database initialization, catalog edits, retriever or provider call is needed.
"""
import os
import sys
import unittest
from unittest.mock import patch

if os.environ.get("TEXEIRA_ISOLATED_TEST") != "1":
    raise RuntimeError("Run tests/run_isolated.py")

import app


CASES = [
    ("fr_equipment", "fr", "Quel équipement dois-je apporter pour le Camino Inca ?"),
    ("fr_clothes", "fr", "Bonjour que dois-je porter pour le Camino Inca ?"),
    ("fr_half_day", "fr", "Je cherche une excursion d'une demi-journée sans randonnée."),
    ("fr_price", "fr", "Quel est le prix du chemin de l'Inca ?"),
    ("fr_unaccented", "fr", "quel equipement dois-je apporter pour le camino inca"),
    ("fr_duration", "fr", "Combien de jours dure le tour Maras Moray ?"),
    ("it_price", "it", "Quanto costa Camino Inca?"),
    ("it_preparation", "it", "Come devo prepararmi per Camino Inca?"),
    ("it_half_day", "it", "Consigliami un tour di mezza giornata senza escursioni a piedi."),
    ("it_schedule", "it", "A che ora parte il tour Maras Moray?"),
    ("it_uppercase", "it", "QUANTO COSTA INKA JUNGLE"),
    ("it_equipment", "it", "Quale attrezzatura devo portare per Camino Inca?"),
    ("pt_price", "pt", "Quanto custa o passeio Maras Moray e o que está incluído?"),
    ("pt_equipment", "pt", "Que equipamento devo levar para Camino Inca?"),
    ("pt_preparation", "pt", "Como devo me preparar para Camino Inca?"),
    ("pt_clothes", "pt", "Que roupa devo usar em Maras Moray?"),
    ("pt_time", "pt", "quatro dias"),
    ("pt_half_day", "pt", "Recomende um passeio de meio dia, não quero fazer caminhadas."),
    ("pt_rejection", "pt", "Nenhum, quero outras opções."),
    ("pt_numeric_two", "pt", "Tenho dois dias e quero caminhar."),
    ("es_price", "es", "¿Cuánto cuesta Camino Inca?"),
    ("es_schedule", "es", "¿A qué hora sale Maras Moray?"),
    ("es_preparation", "es", "¿Cómo me preparo para Camino Inca?"),
    ("es_exclusion", "es", "¿Qué no está incluido en Camino Inca?"),
    ("es_equipment", "es", "que equipo debo llevar a camino inca"),
    ("es_rejection_errata", "es", "ninguno necesito que em recomiendes"),
    ("en_half_day", "en", "half day"),
    ("en_numeric_days", "en", "4 days"),
    ("en_preparation", "en", "How should I prepare for the Inca Trail and what gear is documented?"),
    ("en_recommendation", "en", "Recommend a half day tour without hiking."),
    ("de_price", "de", "Wie viel kostet der Camino Inca?"),
    ("de_preparation", "de", "Was soll ich für den Camino Inca mitbringen?"),
    ("de_recommendation", "de", "Empfehle mir eine Tour für einen halben Tag ohne Wanderung."),
    # English carries the main request; the embedded preference remains ES.
    ("mixed_main_english", "en", "I have medio día y no quiero hiking, what do you recommend?"),
    # Spanish carries the main factual request; English is a courtesy/constraint.
    ("mixed_main_spanish", "es", "precio de Inca Trail please, sin inventar discounts"),
    ("proper_name_camino", "es", "Camino Inca"),
    ("proper_name_jungle", "es", "Inka Jungle"),
    ("proper_name_maras", "es", "Maras Moray"),
]


class LanguageCollisions(unittest.TestCase):
    def test_declared_six_languages_remain_supported(self):
        self.assertEqual(set(app.LANG_MAP), {"es", "en", "pt", "fr", "de", "it"})


def make_case(text, expected):
    def test(self):
        if expected == "de":
            # German still uses the existing local detector and LANG_MAP. This
            # checks that pathway, not accuracy of the probabilistic detector.
            with patch.object(app, "detect", return_value="de") as fallback:
                self.assertEqual(app.detect_language(text), "de", text)
                fallback.assert_called_once_with(text)
            return
        # These explicit cues must decide without probabilistic guesses from
        # short strings or proper names. This blocks, rather than fakes, fallback.
        with patch.object(app, "detect", side_effect=AssertionError("UNEXPECTED_PROBABILISTIC_DETECTION")):
            self.assertEqual(app.detect_language(text), expected, text)
    return test


for case_id, expected, text in CASES:
    setattr(LanguageCollisions, "test_" + case_id, make_case(text, expected))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    unittest.main()
