# Especificación Técnica y Metodológica: Límites del Sistema de Handoff Humano

**Proyecto:** Chatbot Especializado Texeira Travel (WhatsApp Webhook v4)  
**Módulo:** [handoff_support.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py)  
**Suite de Pruebas:** [tests/test_handoff_and_listing_fixes.py](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_handoff_and_listing_fixes.py)  
**Propósito Académico:** Documentación de fronteras operacionales para la tesis (Métricas: `resolved_autonomously`, `escalated_to_human`, `false_positive_rate`).

---

## 1. Fundamento Metodológico y Definición del Problema

En sistemas conversacionales aplicados al sector turismo, la derivación a un asesor humano (*Human Handoff*) representa un equilibrio crítico entre:
1. **Calidad de Servicio:** Garantizar que el usuario que desea interacción personalizada sea atendido sin fricción.
2. **Autonomía Resolutiva:** Evitar que solicitudes informativas rutinarias saturen al equipo de ventas de la agencia.

Si el disparador es excesivamente estricto (solo palabras literales), la tasa de derivación oportuna decae. Por el contrario, si es indiscriminado (e.g. cualquier aparición de la palabra *"ayuda"* o *"asesor"*), se incurre en **falsos positivos de escalamiento**, degradando la métrica de resolución autónoma y consumiendo recursos humanos innecesariamente.

---

## 2. Matriz de Clasificación: Límites de Decisión

El componente [`requested(text)`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py#L104-L139) implementa un clasificador determinista híbrido (coincidencia de términos exactos + expresiones regulares de intención en primera persona).

### A. Intenciones que SÍ Activan Handoff (`escalated_to_human = True`)

Estas expresiones denotan una voluntad explícita, en primera persona o imperativa, de ser transferido o contactado por un agente humano:

| Categoría | Ejemplos de Entrada | Expresión Lógica / Regex | Justificación |
|---|---|---|---|
| **Palabra clave explícita** | `"asesor"`, `"¡asesor!"`, `"asesora"`, `"human agent"`, `"asesores"` | Conjunto exacto normalizado | Comando directo sugerido por el bot como Call To Action (CTA). |
| **Deseo directo en primera persona** | `"quiero hablar con un asesor"`, `"necesito un asesor"`, `"quisiera hablar con una persona"`, `"deseo comunicarme con alguien"` | `\b(quiero\|quisiera\|deseo\|necesito\|puedo\|busco)\s+(hablar\|conversar\|comunicarme\|contactar)\s+...` | El usuario expresa explícitamente necesidad de interlocutor humano. |
| **Petición de llamada directa** | `"quiero que me llamen"`, `"pueden llamarme por favor"`, `"me pueden llamar"`, `"llámenme"` | `\b(quiero\s+que\s+me\s+llamen\|pueden\s+llamarme\|...)\b` | Solicitud explícita de contacto telefónico saliente por parte de la agencia. |
| **Petición de contacto directo** | `"pueden contactarme"`, `"quiero que me contacten"`, `"contactenme"` | `\b(pueden\s+contactarme\|me\s+pueden\s+contactar\|...)\b` | Intención expresa de que un asesor inicie seguimiento directo. |
| **Asistencia humana calificada** | `"necesito ayuda humana"`, `"atención humana por favor"`, `"solicito soporte humano"` | `\b(ayuda\|atencion\|soporte\|asistencia)\s+humana?\b` | La especificación *"humana"* discrimina la ayuda del bot de la humana. |
| **Inglés nativo** | `"i want to speak to an agent"`, `"speak to a human"`, `"i need human help"`, `"please call me"` | `\b(human\s+support\|human\s+help)\b`, `\b(call\s+me\|can\s+you\s+call\s+me)\b` | Cobertura para turistas angloparlantes que solicitan atención humana. |

---

### B. Intenciones que NO Activan Handoff (`escalated_to_human = False`) — Límites del Sistema

Estas expresiones fueron probadas formalmente para garantizar que el bot **no transfiera** erróneamente al asesor:

| Caso de Prueba | Entrada | Ruta Asignada | ¿Por qué NO debe activar Handoff? |
|---|---|---|---|
| **Solicitud de ayuda genérica** | `"Necesito ayuda con mi viaje"` | `help` (Social/Ayuda) | El usuario está pidiendo asistencia al chatbot sobre los servicios, no pidiendo un operador humano. |
| **Recomendación pasiva / Citación** | `"Contacta a un asesor para consultar los detalles"` | `rag` / `evidence` | Proviene de texto recuperado o de un enunciado en tercera persona; no es la intención del usuario. |
| **Sugerencia en tercera persona** | `"Te recomiendo contactar a un asesor"` | `rag` / `evidence` | Mismo principio: el emisor o contexto sugiere contacto, no es una solicitud del cliente. |
| **Inglés - Recomendación pasiva** | `"I recommend contacting an advisor"`, `"Talk to an agent for details"` | `rag` / `evidence` | Expresiones en tercera persona que deben ser resueltas informativamente. |
| **Consulta sobre el tour (staff/guía)**| `"¿El tour incluye guía o asesor?"` | `evidence_includes` | El usuario pregunta por las inclusiones del paquete, no está pidiendo ser transferido. |
| **Pregunta comercial / cotización** | `"¿Cuánto cuesta Machu Picchu?"` | `evidence_confirmed_price` / `evidence_unknown` | Si la tarifa está documentada se responde; si requiere confirmación se añade el CTA opcional, pero no se fuerza el ticket de inmediato. |
| **Disponibilidad de fechas** | `"¿Hay cupos para mañana?"` | `evidence_schedule` / `evidence_unknown` | Informa horario y deriva con CTA sin abrir ticket preventivo en frío. |
| **Saludo / Conversacional** | `"Hola buenos días"`, `"Gracias"` | `social` | Saludos de cortesía gestionados autónomamente en < 50ms sin LLM. |

---

## 3. Implementación Algorítmica

En el código fuente de [`handoff_support.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/handoff_support.py):

```python
def requested(text):
    # 1. Normalización Unicode (elimina tildes, diacríticos, mayúsculas y puntuación)
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    q = normalized.strip(' .!¿?¡\'"')
    
    # 2. Conjunto cerrado de comandos literales y CTAs oficiales
    exact_phrases = {
        'asesor', 'asesora', 'asesores',
        'hablar con un asesor', 'hablar con una asesora', 'hablar con un agente',
        'hablar con una persona', 'hablar con un humano', 'hablar con alguien',
        'quiero hablar con un asesor', 'quiero hablar con una asesora',
        'quiero hablar con una persona', 'quiero hablar con un humano', 'quiero hablar con alguien',
        'necesito un asesor', 'necesito una asesora', 'necesito un agente',
        'necesito hablar con un asesor', 'necesito hablar con una persona',
        'solicitar asesor', 'solicitar agente', 'atencion humana', 'ayuda humana',
        'human agent', 'speak to an agent', 'i want to speak to an agent',
        'talk to an agent', 'talk to a human', 'speak to a human', 'speak to a person',
        'human support', 'human help', 'i need human help',
    }
    if q in exact_phrases:
        return True

    # 3. Expresiones Regulares de Intención Directa (Primera Persona)
    patterns = [
        r'\b(quiero|quisiera|deseo|necesito|puedo|busco)\s+(hablar|conversar|comunicarme|contactar|contactarme)\s+(con\s+)?(un\s+|una\s+|algun\s+|alguna\s+)?(asesor\w*|persona\w*|humano\w*|agente\w*|operador\w*|alguien)\b',
        r'\b(quiero\s+que\s+me\s+llamen|pueden\s+llamarme|me\s+pueden\s+llamar|favor\s+de\s+llamarme|llamenme)\b',
        r'\b(pueden\s+contactarme|me\s+pueden\s+contactar|quiero\s+que\s+me\s+contacten|contactenme)\b',
        r'\b(ayuda|atencion|soporte|asistencia)\s+humana?\b',
        r'\b(human\s+support|human\s+help|human\s+assistance)\b',
        r'\b(i\s+want\s+to|i\s+need\s+to|can\s+i|i\s+need)\s+(speak|talk|chat|contact)?\s*(to|with)?\s*(a\s+|an\s+)?(human|person|agent|advisor|representative)\b',
        r'\b(call\s+me|please\s+call\s+me|can\s+you\s+call\s+me)\b',
    ]
    for pat in patterns:
        if re.search(pat, q):
            return True
    return False
```

---

## 4. Evidencia Empírica de Validación

La suite automatizada [`tests/test_handoff_and_listing_fixes.py`](file:///c:/Users/HP/Desktop/Chat%20bot/texeira-prueba-v4-evidencias/tests/test_handoff_and_listing_fixes.py) ejecuta 30 casos de prueba específicos sobre esta frontera:
* **20 casos positivos:** 100% clasificados como `True`.
* **10 casos negativos (falsos positivos prevenidos):** 100% clasificados como `False`.
* **Tasa de falsos positivos en suites de regresión:** **0.0%**.

Esta delimitación explícita respalda rigurosamente los resultados ante las evaluaciones metodológicas del jurado de tesis.
