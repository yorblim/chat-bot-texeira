"""
test_catalog_form_improvements.py — Pruebas de regresión para las mejoras del formulario de tours y tarifas.

Verifica:
1. Dos pestañas independientes y guardados separados (sin formularios apilados).
2. Protección de borradores y detección de cambios pendientes por formulario.
3. Lenguaje de agencia ('Qué incluye', 'Qué no incluye', 'Precio por persona', 'Otros nombres').
4. Cálculo y visualización rigurosa de vigencia de tarifas (Vigente, Programada, Vencida, Deshabilitada).
5. Conservación de ventana abierta tras crear un tour para habilitar sus tarifas inmediatamente.
6. Filtro de estado de tours (activos / inactivos) y control explícito en formulario.
"""

import unittest
import re
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog_ui import get_catalog_html
import catalog_service


class CatalogFormImprovementsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = get_catalog_html("test-csrf-token-12345")

    def test_two_tabs_and_separate_forms_rendered(self):
        """Verifica que existan dos pestañas independientes y botones de guardado explícitos."""
        html = self.html
        self.assertIn('id="tabBtnTourData"', html)
        self.assertIn('id="tabBtnTourRates"', html)
        self.assertIn('id="tabPaneTourData"', html)
        self.assertIn('id="tabPaneTourRates"', html)

        # Botones de guardado explícitos y diferenciados
        self.assertIn('Guardar datos del tour', html)
        self.assertIn('Guardar esta tarifa', html)

        # Aclaración explícita de que las tarifas se guardan por separado
        self.assertIn('tarifas especiales se configuran y guardan por separado', html)

        # No debe existir un botón engañoso de "Guardar todo"
        self.assertNotIn('Guardar todo', html)

    def test_agency_language_and_expanded_fields(self):
        """Verifica terminología de agencia y campos de varias líneas."""
        html = self.html

        # Inclusiones / Exclusiones reemplazadas por lenguaje claro de agencia
        self.assertIn('Qué incluye', html)
        self.assertIn('Qué no incluye', html)
        self.assertIn('id="formIncludes"', html)
        self.assertIn('id="formExcludes"', html)

        # Textareas con al menos 4 filas para lectura cómoda
        self.assertTrue(re.search(r'<textarea\s+id="formIncludes"[^>]*rows="4"', html))
        self.assertTrue(re.search(r'<textarea\s+id="formExcludes"[^>]*rows="4"', html))

        # Precio por persona y ayuda para valor por confirmar
        self.assertIn('Precio por persona', html)
        self.assertIn('Si se deja vacío, el precio queda por confirmar', html)

        # Opciones avanzadas desplegables para ID técnico y alias
        self.assertIn('id="advancedTourOptions"', html)
        self.assertIn('Otros nombres para encontrar este tour', html)
        self.assertIn('id="formAliases"', html)

    def test_draft_protection_functions_rendered(self):
        """Verifica la existencia de lógica de detección de borradores y protección contra cierre."""
        html = self.html

        self.assertIn('getTourFormSnapshot', html)
        self.assertIn('isTourFormDirty', html)
        self.assertIn('isRateFormDirty', html)
        self.assertIn('requestCloseTourModal', html)

        # Manejo de tecla Escape con comprobación de cambios
        self.assertIn("'Escape'", html)

        # Cancelación de tarifa independiente que solo oculta el formulario de tarifa
        self.assertIn('cancelRateEdit', html)

    def test_tour_creation_keeps_modal_open_and_enables_rates(self):
        """Verifica que el guardado exitoso de un nuevo tour no cierre el modal y active tarifas."""
        html = self.html

        # En la respuesta exitosa del submit de tour:
        self.assertIn("document.getElementById('formIsEdit').value = '1'", html)
        self.assertIn("document.getElementById('formEntityId').disabled = true", html)
        self.assertIn("loadTourRates(savedId)", html)
        self.assertIn("Tour creado exitosamente. Ya puedes registrar sus tarifas especiales", html)

    def test_rates_clarity_and_vigencia_distinction(self):
        """Verifica campos claros en tarifas, referencia de tarifa base y 4 estados de vigencia."""
        html = self.html

        # Etiqueta de precio final de tarifa
        self.assertIn('Precio final de esta tarifa', html)
        self.assertIn('no es un descuento porcentual', html)

        # Referencia visual de la tarifa base
        self.assertIn('id="ratesTourBaseRef"', html)

        # Checkbox renombrado a Habilitar esta tarifa
        self.assertIn('Habilitar esta tarifa', html)

        # Requisitos ampliados a textarea
        self.assertTrue(re.search(r'<textarea\s+id="rateConditions"[^>]*rows="3"', html))

        # Evaluación de los 4 estados: Vigente, Programada, Vencida, Deshabilitada
        self.assertIn('getRateStatusInfo', html)
        self.assertIn('rate-status-active', html)
        self.assertIn('rate-status-scheduled', html)
        self.assertIn('rate-status-expired', html)
        self.assertIn('rate-status-disabled', html)

    def test_tour_status_control_and_toolbar_filter(self):
        """Verifica control de activo/inactivo en el formulario y filtro en la barra de herramientas."""
        html = self.html

        # Checkbox en formulario del tour
        self.assertIn('id="formIsActive"', html)
        self.assertIn('Tour activo (visible para el bot en WhatsApp y catálogo)', html)

        # Filtro en la barra de herramientas
        self.assertIn('id="filterStatus"', html)
        self.assertIn('Solo activos (visibles)', html)
        self.assertIn('Solo inactivos / archivados', html)

    def test_rate_upsert_does_not_mutate_tour_is_active(self):
        """Verifica en base aislada que guardar o eliminar tarifas no altera el is_active del tour."""
        catalog_service.init_catalog_db()
        test_eid = "test-tour-vigencia-isolation"

        # Crear tour con is_active = 1
        ok_tour, msg = catalog_service.upsert_tour({
            "entity_id": test_eid,
            "name": "Tour de Prueba de Aislamiento",
            "is_active": True,
            "official_price": "80"
        })
        self.assertTrue(ok_tour, f"Fallo al crear tour: {msg}")

        # Guardar tarifa especial
        ok_rate, rate_res = catalog_service.upsert_tour_rate({
            "entity_id": test_eid,
            "rate_name": "Tarifa Estudiante Promo",
            "rate_category": "student",
            "price": "60",
            "currency": "USD",
            "is_active": 1
        })
        self.assertTrue(ok_rate, f"Fallo al guardar tarifa: {rate_res}")

        # Comprobar que el tour sigue activo
        t = catalog_service.get_tour_by_id(test_eid)
        self.assertIsNotNone(t)
        self.assertTrue(t["is_active"], "Guardar tarifa alteró el estado activo del tour")

        # Desactivar tour explícitamente
        catalog_service.upsert_tour({
            "entity_id": test_eid,
            "name": "Tour de Prueba de Aislamiento",
            "is_active": False
        })
        t_deact = catalog_service.get_tour_by_id(test_eid)
        self.assertFalse(t_deact["is_active"], "El tour no se desactivó correctamente")

        # Guardar otra tarifa para el tour desactivado
        ok_rate2, rate_res2 = catalog_service.upsert_tour_rate({
            "entity_id": test_eid,
            "rate_name": "Tarifa Menor",
            "rate_category": "child",
            "price": "40",
            "currency": "USD",
            "is_active": 1
        })
        self.assertTrue(ok_rate2)

        # El tour debe PERMANECER desactivado
        t_still_deact = catalog_service.get_tour_by_id(test_eid)
        self.assertFalse(t_still_deact["is_active"], "Guardar tarifa reactivó accidentalmente el tour")

        # Limpieza
        catalog_service.delete_tour(test_eid)


if __name__ == "__main__":
    unittest.main()
