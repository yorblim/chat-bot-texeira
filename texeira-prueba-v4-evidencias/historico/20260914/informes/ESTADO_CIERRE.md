# Estado de cierre del prototipo Texeira

Fecha: 11 de septiembre de 2026

## Fases completadas

### Fase 1: Punto de partida
- Archivos leídos: PLAN_FINAL_OPENCODE.md, CONTINUAR_EN_OPENCODE.md, REVISION_OPENCODE.md
- Backup creado: app_backup.ps1, trial_support_backup.ps1
- Versión actual: app.py con correcciones de needs_escalation y rag_chain

### Fase 2: Corrección de cuatro fallos verificados
Los cuatro fallos identificados en REVISION_OPENCODE.md han sido corregidos:

1. **Derivación falsa** (app.py:568-608)
   - Eliminado "contacta a" de escalation_indicators
   - Solo detecta transferencia efectiva, no orientación
   - Verificado: `is_escalation=False` para "Contacta a un asesor para consultar los detalles"

2. **Corrección de contacto** (app.py:968-982)
   - Post-procesamiento ahora usa regex para mayor flexibilidad
   - Detecta variaciones como "fuentes de precios" y "enlaces de las fuentes"
   - Reemplaza con contacto publicado de data/provisional.json

3. **Condiciones pendientes en rutas deterministas** (trial_support.py:139-152)
   - Añadida detección de `needs_agency_conf` en ruta determinista
   - Cubre: soles/pen/tipo de cambio, disponibilidad/reserva, pagos/adelantos
   - Verificado: `needs_agency_confirmation=True` para "¿Cuál es el precio en soles de Salkantay?"

4. **Historial guarda texto post-procesado** (app.py:952-997)
   - Movido `add_to_history` después del post-procesamiento
   - Historial ahora contiene la respuesta final modificada
   - Verificado: respuesta e historial coinciden

5. **Mejora adicional: palabras clave en inglés** (app.py:959-964)
   - Añadidas palabras clave para disponibilidad, pagos y conversiones en inglés
   - Verificado: `needs_agency_confirmation=True` para "Is there availability for tomorrow?"

### Fase 3: Regresión local sin API
- Ejecutado: `test_trial.py` → OK
- Ejecutado: `test_four_fallos.py` → OK (todas las aserciones pasan)
- Ejecutado: `evaluate_ten.py local` → OK
- Resultados: C06, C07, C08, C09, C10 con indicadores correctos

### Fase 4: Comprobación de la copia en ejecución
- Servidor verificado en puerto 8020 (PID 21208)
- Reiniciado para aplicar correcciones
- Prueba en vivo de 4 casos afectados:
  - C06: `escalation=False` ✓
  - C07: `resolved=False, needs_confirm=True` ✓
  - C08: `resolved=False, needs_confirm=True` ✓
  - C09: `resolved=False, needs_confirm=True` ✓

### Fase 5: Evaluación y documentación técnica
- Informe antes/después: INFORME_ANTES_DESPUES.md
- Evidencia: evaluation-ten-local-20260911-153941.json
- Pruebas: test_trial.py OK, test_four_fallos.py OK, evaluate_ten.py OK

### Fase 5b: Verificación de los 4 puntos de REVISION_OPENCODE.md
- Prueba: test_revision_4puntos.py → 4/4 OK
- Punto 1: "Derivación falsa" → is_escalation=False ✓
- Punto 2: "Contacto de agencia" → sin fuentes externas, con teléfonos ✓
- Punto 3: "Ruta determinista" → needs_agency_confirmation=True, route=provisional_catalog ✓
- Punto 4: "Historial post-procesado" → respuesta e historial coinciden ✓

### Fase 5c: Contacto de agencia en respuestas
- Post-procesamiento agrega teléfonos (+51 953 767 860 / +51 984 679 715) y dirección cuando la respuesta sugiere contactar a la agencia
- Verificado en vivo para "¿Puedo pagar con Yape?" y "¿Hay cupos para mañana?"

## Pendientes

### Fase 6: Validación de datos con la agencia
- FICHA_VALIDACION_AGENCIA.md creada con tours, inclusiones, contactos y fechas
- [ ] Confirmar tours/variantes ofrecidos
- [ ] Confirmar inclusiones/exclusiones
- [ ] Confirmar políticas de reservas/pago/cancelación
- [ ] Confirmar contactos
- Los rangos de precios son estimaciones de mercado; precios oficiales sujetos a cotización

### Fase 7: Preparar entrega
- [x] Crear GUIA_PRUEBAS.md
- [x] Crear DIFF_CAMBIOS.md
- [x] Crear REVERSION.md
- [x] Crear backups (app_final.ps1, trial_support_final.ps1)
- [ ] Integración al original (requiere autorización)
- [ ] Publicación/envío de mensajes (requiere autorización)

## Limitaciones conocidas
- Precios son estimaciones, no tarifas oficiales
- Inclusiones son escenarios simulados
- Políticas de reserva/pago/cancelación no confirmadas
- No hay conexión a inventario real
- No hay sistema de derivación a asesores
- Detección de idioma limitada a 4 idiomas
- Post-procesamiento depende de keywords específicas
- El LLM puede generar respuestas que no activan los patrones de detección

## Arquitectura utilizada
- **Framework**: FastAPI (app.py)
- **Retriever**: Híbrido BM25 + Vectorial con RRF (src/retriever.py)
- **Embeddings**: HuggingFace (offline)
- **Base vectorial**: ChromaDB (chroma_provisional_db/)
- **LLM**: Configurable (DeepSeek/Groq/OpenAI/Anthropic)
- **Prompt**: System prompt estricto con reglas de handoff
- **Detección de idioma**: langdetect + reglas por palabras clave
- **Historial**: Memoria de corto plazo por usuario (últimos 10 turnos)
- **Adaptador**: trial_support.py (solo para copia de prueba)

## Cómo iniciar la copia de prueba
```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
.\INICIAR.ps1
```
El servidor estará disponible en http://127.0.0.1:8020/chat

## Pruebas realizadas
```bash
python test_trial.py              # Pruebas de integración
python test_four_fallos.py        # Pruebas de los 4 fallos
python test_revision_4puntos.py   # Prueba de los 4 puntos de REVISION_OPENCODE.md
python evaluate_ten.py local      # Evaluación de 10 casos con LLM simulado
```

## Dependencias pendientes
- Confirmación de datos con la agencia (fase 6)
- Autorización para llamadas reales a IA
- Autorización para integración al original
- Autorización para publicación/envío de mensajes

## Archivos modificados
- `app.py`: needs_escalation, rag_chain (post-procesamiento, historial, keywords)
- `trial_support.py`: ruta determinista con needs_agency_conf

## Archivos creados
- `test_four_fallos.py`: prueba específica de los cuatro fallos corregidos
- `test_revision_4puntos.py`: prueba de los 4 puntos de REVISION_OPENCODE.md
- `INFORME_ANTES_DESPUES.md`: informe técnico antes/después
- `FICHA_VALIDACION_AGENCIA.md`: ficha para confirmar datos con la agencia
- `GUIA_PRUEBAS.md`: guía breve de pruebas para el grupo
- `DIFF_CAMBIOS.md`: diff de cambios vs backup original
- `REVERSION.md`: instrucciones de reversión
- `README.md`: guía de uso de la copia de prueba
- `ESTADO_CIERRE.md`: este archivo
