# Diff de Cambios - Prototipo Texeira v2

**Fecha**: 11 de septiembre de 2026
**Archivos modificados**: app.py, trial_support.py
**Backup original**: app_backup.ps1, trial_support_backup.ps1

---

## 1. Cambios en app.py

### 1.1 Correccion #1: needs_escalation (lineas ~568-608)

**ANTES** (app_backup.ps1):
```python
escalation_indicators = [
    "contacta a un asesor",
    "contacta a un agente",
    "transferirte a un asesor",
    # ... mas indicadores
]
```

**DESPUES** (app.py):
```python
escalation_indicators = [
    # "contacta a un asesor" ELIMINADO - es orientacion, no transferencia
    "transferirte a un asesor",
    "te conecto con un asesor",
    # ... solo transferencias efectivas
]
```

**Razon**: "Contacta a un asesor" es orientacion al usuario, no una transferencia ejecutada.

---

### 1.2 Correccion #2: Post-procesamiento de contacto (lineas ~968-982)

**ANTES** (app_backup.ps1):
```python
if "fuentes de precios" in response_text.lower():
    response_text = response_text.replace(
        "fuentes de precios",
        "datos de contacto de la agencia"
    )
```

**DESPUES** (app.py):
```python
# Cargar datos de contacto de la agencia
import json
from pathlib import Path
catalog_path = Path(__file__).parent / "data" / "provisional.json"
agency_contact = ""
if catalog_path.exists():
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    agency = catalog.get("agency", {})
    phone1 = agency.get("published_phone", "+51 953 767 860")
    phone2 = agency.get("published_secondary_phone", "+51 984 679 715")
    address = agency.get("published_address", "Calle Carmen Quicllu N.º 250, Cusco")
    agency_contact = f"\n\nPara contactar a la agencia:\n- Teléfonos: {phone1} / {phone2}\n- Dirección: {address}"

# Reemplazos con regex
import re as _re_contact
response_text = _re_contact.sub(r'fuentes de precios.*?agencia', '', response_text)
response_text = _re_contact.sub(r'enlaces de las fuentes.*?agencia', '', response_text)

# Agregar contacto si la respuesta sugiere contactar la agencia
if ('contactar' in response_text.lower() or 'canales oficiales' in response_text.lower()) and '+51' not in response_text:
    response_text = response_text.rstrip() + agency_contact
```

**Razon**: Reemplazar enlaces de otros operadores con datos reales de Texeira.

---

### 1.3 Correccion #3: Historial post-procesado (lineas ~990-997)

**ANTES** (app_backup.ps1):
```python
add_to_history(user_id, "human", question)
add_to_history(user_id, "ai", response_text)  # Antes del post-procesamiento
# ... post-procesamiento ...
```

**DESPUES** (app.py):
```python
# ... post-procesamiento ...
add_to_history(user_id, "human", question)
add_to_history(user_id, "ai", response_text)  # Despues del post-procesamiento
```

**Razon**: El historial debe guardar la respuesta final, no la original.

---

### 1.4 Correccion #4: Keywords en ingles (lineas ~949-955)

**ANTES** (app_backup.ps1):
```python
if any(kw in q_lower for kw in ["yape", "adelanto", "pago", "pagar"]):
    needs_agency_conf = True
if any(kw in q_lower for kw in ["cupo", "cupos", "disponibilidad"]):
    needs_agency_conf = True
```

**DESPUES** (app.py):
```python
if any(kw in q_lower for kw in ["yape", "adelanto", "pago", "pagar", "payment", "deposit"]):
    needs_agency_conf = True
if any(kw in q_lower for kw in ["cupo", "cupos", "disponibilidad", "availability", "reservation", "book"]):
    needs_agency_conf = True
if any(kw in q_lower for kw in ["soles", "pen", "tipo de cambio", "exchange rate"]):
    needs_agency_conf = True
```

**Razon**: Soporte para preguntas en ingles.

---

## 2. Cambios en trial_support.py

### 2.1 Correccion #5: Condiciones pendientes en ruta determinista (lineas ~139-152)

**ANTES** (trial_support_backup.ps1):
```python
text = NOTICES['es'] + '\n\n' + NAMES[i] + '\n' + '\n'.join(parts)
ns['add_to_history'](user_id,'human',question)
ns['add_to_history'](user_id,'ai',text)
return {'response': text, 'context_used': True, 'is_predefined': True, 'is_fallback': False, 'route': 'provisional_catalog'}
```

**DESPUES** (trial_support.py):
```python
text = NOTICES['es'] + '\n\n' + NAMES[i] + '\n' + '\n'.join(parts)
# Detectar condiciones pendientes en rutas deterministas
needs_agency_conf = False
if any(x in q for x in ['soles','pen','tipo de cambio','conversión','conversion']):
    needs_agency_conf = True
if any(x in q for x in ['cupo','cupos','disponibilidad','reserva','reservar','confirmar reserva']):
    needs_agency_conf = True
if any(x in q for x in ['yape','adelanto','pago','pagar','forma de pago','depósito','deposito']):
    needs_agency_conf = True
ns['add_to_history'](user_id,'human',question)
ns['add_to_history'](user_id,'ai',text)
return {'response': text, 'context_used': True, 'is_predefined': True, 'is_fallback': False,
        'resolved_autonomously': not needs_agency_conf,
        'needs_agency_confirmation': needs_agency_conf,
        'route': 'provisional_catalog'}
```

**Razon**: Las rutas deterministas tambien deben marcar condiciones pendientes.

---

### 2.2 Correccion #6: Historial en respuesta LLM (lineas ~149-160)

**ANTES** (trial_support_backup.ps1):
```python
result = original(question,user_id)
notice = NOTICES.get(lang,NOTICES['es'])
if not result['response'].startswith(notice): result['response'] = notice + '\n\n' + result['response']
return result
```

**DESPUES** (trial_support.py):
```python
result = original(question,user_id)
notice = NOTICES.get(lang,NOTICES['es'])
if not result['response'].startswith(notice): result['response'] = notice + '\n\n' + result['response']
# Re-guardar en historial con la respuesta final (incluye NOTICES y post-procesamiento)
ns['add_to_history'](user_id, 'human', question)
ns['add_to_history'](user_id, 'ai', result['response'])
return result
```

**Razon**: El historial debe contener la respuesta final con NOTICES y post-procesamiento.

---

## 3. Resumen de cambios

| Archivo | Cambios | Lineas afectadas |
|---------|---------|------------------|
| app.py | needs_escalation, post-procesamiento, historial, keywords | ~568-608, ~949-997 |
| trial_support.py | ruta determinista, historial LLM | ~139-160 |

## 4. Archivos de respaldo

| Archivo | Contenido |
|---------|-----------|
| app_backup.ps1 | app.py original antes de cambios |
| trial_support_backup.ps1 | trial_support.py original antes de cambios |
| app_final.ps1 | app.py version final |
| trial_support_final.ps1 | trial_support.py version final |
