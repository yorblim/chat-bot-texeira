"""
tests/test_tour_date_availability.py — Suite completa de pruebas para disponibilidad por fecha específica.

Valida:
1. Esquema y persistencia en catalog_tour_dates (CRUD, upsert, eliminación por ID y por fecha).
2. Parser conversacional de fechas en lenguaje natural (ES, EN, PT, relativos e ISO).
3. Formateador localizado de fechas.
4. Respuestas deterministas del bot en verified_routes ante fechas agotadas, limitadas o disponibles.
5. Etiquetado de tickets de reserva y derivación (handoff) ante fechas agotadas o con cupos limitados.
"""

import unittest
from datetime import date, timedelta, datetime, timezone
import catalog_service
from db_adapter import get_db_session


class TestTourDateAvailability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog_service.init_catalog_db()

    def setUp(self):
        # Limpiar registros previos de fechas de prueba
        with get_db_session() as conn:
            conn.execute("DELETE FROM catalog_tour_dates WHERE entity_id IN ('city-tour-cusco', 'valle-sagrado', 'montana-7-colores')")
        catalog_service.invalidate_catalog_cache()

    def tearDown(self):
        with get_db_session() as conn:
            conn.execute("DELETE FROM catalog_tour_dates WHERE entity_id IN ('city-tour-cusco', 'valle-sagrado', 'montana-7-colores')")
        catalog_service.invalidate_catalog_cache()

    # --------------------------------------------------------------------------
    # 1. PARSER Y FORMATEADOR DE FECHAS
    # --------------------------------------------------------------------------

    def test_parse_date_relative_dates(self):
        ref = date(2026, 10, 17)
        # Hoy
        self.assertEqual(catalog_service.parse_date_from_query("hay tour hoy?", reference_date=ref), ref)
        self.assertEqual(catalog_service.parse_date_from_query("spots today please", reference_date=ref), ref)
        self.assertEqual(catalog_service.parse_date_from_query("tem saida hoje?", reference_date=ref), ref)

        # Mañana
        tomorrow = ref + timedelta(days=1)
        self.assertEqual(catalog_service.parse_date_from_query("mañana tienen city tour?", reference_date=ref), tomorrow)
        self.assertEqual(catalog_service.parse_date_from_query("manana por favor", reference_date=ref), tomorrow)
        self.assertEqual(catalog_service.parse_date_from_query("is there a tour tomorrow?", reference_date=ref), tomorrow)
        self.assertEqual(catalog_service.parse_date_from_query("tem vaga amanha?", reference_date=ref), tomorrow)

        # Pasado mañana
        day_after = ref + timedelta(days=2)
        self.assertEqual(catalog_service.parse_date_from_query("pasado mañana sale?", reference_date=ref), day_after)
        self.assertEqual(catalog_service.parse_date_from_query("the day after tomorrow", reference_date=ref), day_after)
        self.assertEqual(catalog_service.parse_date_from_query("depois de amanha", reference_date=ref), day_after)

    def test_parse_date_iso_and_slash_formats(self):
        ref = date(2026, 10, 17)
        # ISO
        self.assertEqual(catalog_service.parse_date_from_query("fecha 2026-11-20", reference_date=ref), date(2026, 11, 20))
        # Slash con año
        self.assertEqual(catalog_service.parse_date_from_query("salida el 15/11/2026", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("salida el 15-11-2026", reference_date=ref), date(2026, 11, 15))
        # Slash sin año con contexto
        self.assertEqual(catalog_service.parse_date_from_query("para el 15/11", reference_date=ref), date(2026, 11, 15))

    def test_parse_date_natural_language_multilingual(self):
        ref = date(2026, 10, 17)
        # Español
        self.assertEqual(catalog_service.parse_date_from_query("15 de noviembre", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("15 de noviembre de 2026", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("noviembre 15", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("25 dic", reference_date=ref), date(2026, 12, 25))

        # Inglés
        self.assertEqual(catalog_service.parse_date_from_query("November 15", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("Nov 15th 2026", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("15th of november", reference_date=ref), date(2026, 11, 15))

        # Portugués
        self.assertEqual(catalog_service.parse_date_from_query("15 de novembro", reference_date=ref), date(2026, 11, 15))
        self.assertEqual(catalog_service.parse_date_from_query("dia 20 de dezembro", reference_date=ref), date(2026, 12, 20))

    def test_format_date_localized(self):
        d = date(2026, 11, 15)
        self.assertEqual(catalog_service.format_date_localized(d, "es"), "15 de noviembre de 2026")
        self.assertEqual(catalog_service.format_date_localized(d, "en"), "November 15, 2026")
        self.assertEqual(catalog_service.format_date_localized(d, "pt"), "15 de novembro de 2026")

    # --------------------------------------------------------------------------
    # 2. PERSISTENCIA Y CRUD EN BASE DE DATOS (catalog_tour_dates)
    # --------------------------------------------------------------------------

    def test_crud_tour_blocked_date(self):
        eid = "city-tour-cusco"
        t_date = "2026-11-20"

        # 1. Crear bloqueo
        ok, res = catalog_service.upsert_tour_blocked_date({
            "entity_id": eid,
            "tour_date": t_date,
            "status": "sold_out",
            "notes": "Grupo corporativo cerrado"
        })
        self.assertTrue(ok)
        date_id = res

        # 2. Consultar fecha bloqueada
        dates = catalog_service.get_tour_blocked_dates(eid, future_only=False)
        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0]["tour_date"], t_date)
        self.assertEqual(dates[0]["status"], "sold_out")
        self.assertEqual(dates[0]["notes"], "Grupo corporativo cerrado")

        # 3. Consultar disponibilidad en esa fecha específica
        info = catalog_service.get_tour_availability_on_date(eid, t_date)
        self.assertEqual(info["status"], "sold_out")
        self.assertTrue(info["is_date_specific"])
        self.assertEqual(info["notes"], "Grupo corporativo cerrado")
        self.assertTrue(catalog_service.is_sold_out_on_date(eid, t_date))

        # 4. Actualizar a cupos limitados (upsert sobre la misma fecha)
        ok_up, res_up = catalog_service.upsert_tour_blocked_date({
            "entity_id": eid,
            "tour_date": t_date,
            "status": "limited",
            "notes": "Últimos 3 espacios"
        })
        self.assertTrue(ok_up)
        info_up = catalog_service.get_tour_availability_on_date(eid, t_date)
        self.assertEqual(info_up["status"], "limited")
        self.assertEqual(info_up["notes"], "Últimos 3 espacios")
        self.assertFalse(catalog_service.is_sold_out_on_date(eid, t_date))

        # 5. Eliminar bloqueo por fecha
        del_ok, del_msg = catalog_service.delete_tour_blocked_date(t_date, entity_id=eid)
        self.assertTrue(del_ok)
        info_after = catalog_service.get_tour_availability_on_date(eid, t_date)
        self.assertFalse(info_after["is_date_specific"])
        self.assertEqual(info_after["status"], "available")

    # --------------------------------------------------------------------------
    # 3. RESPUESTAS EN VERIFIED_ROUTES
    # --------------------------------------------------------------------------

    def test_verified_routes_date_sold_out_response(self):
        import app
        eid = "city-tour-cusco"
        t_date = "2026-11-20"

        # Marcar fecha específica como sold_out
        catalog_service.upsert_tour_blocked_date({
            "entity_id": eid,
            "tour_date": t_date,
            "status": "sold_out",
            "notes": "Cupos de tren agotados"
        })

        from app import rag_chain
        # Consulta en español
        res_es = rag_chain(f"Hay cupo para City Tour el {t_date}?", user_id="test_user_date_1")
        self.assertEqual(res_es.get("route"), "evidence_availability")
        self.assertIn("City Tour Cusco", res_es.get("response", ""))
        self.assertIn("agotados", res_es.get("response", "").lower())
        self.assertIn("20 de noviembre de 2026", res_es.get("response", ""))
        self.assertIn("Cupos de tren agotados", res_es.get("response", ""))

        # Consulta en inglés
        res_en = rag_chain("Do you have spots for City Tour on November 20, 2026?", user_id="test_user_date_2")
        self.assertEqual(res_en.get("route"), "evidence_availability")
        self.assertIn("sold out", res_en.get("response", "").lower())
        self.assertIn("November 20, 2026", res_en.get("response", ""))

    def test_verified_routes_date_limited_response(self):
        from app import rag_chain
        eid = "montana-7-colores"
        t_date = "2026-11-25"

        catalog_service.upsert_tour_blocked_date({
            "entity_id": eid,
            "tour_date": t_date,
            "status": "limited",
            "notes": "Quedan 4 cupos"
        })

        res = rag_chain(f"Disponibilidad montaña 7 colores {t_date}", user_id="test_user_date_3")
        self.assertEqual(res.get("route"), "evidence_availability")
        self.assertIn("cupos limitados", res.get("response", "").lower())
        self.assertIn("25 de noviembre de 2026", res.get("response", ""))

    def test_verified_routes_date_available_response(self):
        from app import rag_chain
        # Fecha no bloqueada
        res = rag_chain("Tienen salidas para Valle Sagrado el 15 de diciembre de 2026?", user_id="test_user_date_4")
        self.assertEqual(res.get("route"), "evidence_availability")
        self.assertIn("cupos disponibles", res.get("response", "").lower())
        self.assertIn("15 de diciembre de 2026", res.get("response", ""))

    # --------------------------------------------------------------------------
    # 4. RESERVAS Y DERIVACIÓN A ASESOR (HANDOFF TAGGING)
    # --------------------------------------------------------------------------

    def test_handoff_booking_tagged_with_sold_out_date(self):
        from app import rag_chain
        import app
        import handoff_support
        from handoff_support import apply_request
        eid = "city-tour-cusco"
        t_date = "2026-11-20"

        # Marcar fecha como sold_out
        catalog_service.upsert_tour_blocked_date({
            "entity_id": eid,
            "tour_date": t_date,
            "status": "sold_out",
            "notes": "Capacidad máxima de buses"
        })

        uid = "test_user_booking_sold_out"
        # Limpiar solicitudes previas del usuario
        with handoff_support.connection() as conn:
            conn.execute("DELETE FROM requests WHERE user_id = ?", (uid,))

        question = f"Quiero reservar City Tour para el {t_date}"
        rag_res = rag_chain(question, user_id=uid)
        res = apply_request(app.__dict__, rag_res, uid, "whatsapp", question)
        self.assertTrue(res.get("handoff_registered"))
        self.assertIn("cupos agotados", res.get("response", "").lower())

        # Verificar ticket en la base de datos
        with handoff_support.connection() as conn:
            row = conn.execute("SELECT * FROM requests WHERE user_id = ?", (uid,)).fetchone()
            self.assertIsNotNone(row)
            question_stored = row["question"] if hasattr(row, "__getitem__") else row[3]
            self.assertIn("[Reserva - FECHA AGOTADA: 2026-11-20", question_stored)
            self.assertIn("City Tour Cusco", question_stored)


if __name__ == '__main__':
    unittest.main()
