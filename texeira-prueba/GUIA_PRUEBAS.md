# Guia de Pruebas - Prototipo Texeira (v2)

**Objetivo**: Verificar que los 4 fallos corregidos funcionan correctamente.

---

## 1. Iniciar el servidor

```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
.\INICIAR.ps1
```

Abrir en el navegador: **http://127.0.0.1:8020/chat**

---

## 2. Prueba manual (5 minutos)

Escribir estas 4 preguntas en el chat y verificar la respuesta:

### Pregunta 1: "Contacta a un asesor para consultar los detalles"
- **Resultado esperado**: `is_escalation=false` (no debe mostrar "Conectando con asesor")
- **Por que**: Es una recomendacion, no una transferencia real

### Pregunta 2: "¿Cuanto cuesta el tour de Valle Sagrado?"
- **Resultado esperado**: Respuesta con rango USD 40-60, sin "fuentes de precios"
- **Por que**: Precio referencial conocido

### Pregunta 3: "¿Puedo pagar con Yape?"
- **Resultado esperado**: `needs_agency_confirmation=true`, con电话 +51 953 767 860
- **Por que**: Metodo de pago no confirmado

### Pregunta 4: "¿Hay cupos para manana?"
- **Resultado esperado**: `needs_agency_confirmation=true`, con电话 +51 953 767 860
- **Por que**: Disponibilidad no confirmada

---

## 3. Prueba automatica

```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
python test_revision_4puntos.py
```

Salida esperada:
```
=== PUNTO 1: Derivacion falsa ===
OK: recomendacion no es derivacion

=== PUNTO 2: Contacto de agencia ===
OK: sin fuentes externas, con contacto Texeira

=== PUNTO 3: Ruta determinista ===
OK: ruta determinista marca condicion pendiente

=== PUNTO 4: Historial post-procesado ===
OK: historial guarda texto post-procesado

=== LOS 4 PUNTOS PASARON ===
```

---

## 4. Prueba completa (opcional)

```bash
python test_trial.py              # Integracion
python test_four_fallos.py        # Los 4 fallos
python evaluate_ten.py local      # 10 casos
```

---

## 5. Indicadores clave

| Indicador | Que significa | Valor correcto |
|-----------|---------------|----------------|
| `resolved_autonomously` | El bot resolvio sin intervencion humana | true en preguntas informativas, false en condiciones comerciales |
| `needs_agency_confirmation` | Requiere confirmacion de Texeira | true en pagos, disponibilidad, precios exactos |
| `escalated_to_human` | Transferencia a asesor | false (nunca se transfiere automaticamente) |

---

## 6. Errores conocidos

- Los precios son **estimaciones**, no tarifas oficiales
- No hay conexion a inventario real de reservas
- El bot no puede confirmar disponibilidad

---

## 7. Contacto

Para dudas, contactar al equipo de desarrollo.
