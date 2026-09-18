# Copia de prueba Texeira - Guía de uso

## Iniciar el servidor

```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
.\INICIAR.ps1
```

El servidor estará disponible en: http://127.0.0.1:8020/chat

**Nota**: El buscador tarda ~30 segundos en precargar. El servidor acepta solicitudes después.

## Probar el bot

### Opción 1: Interfaz web
1. Abrir http://127.0.0.1:8020/chat
2. Escribir una pregunta
3. Verificar respuesta e indicadores

### Opción 2: API directa
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8020/test-chat" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"user_id":"test","message":"¿Qué tours tienen?"}'
```

### Opción 3: Scripts de prueba
```bash
python test_trial.py          # Pruebas de integración
python test_four_fallos.py    # Prueba de 4 fallos corregidos
python evaluate_ten.py local  # Evaluación de 10 casos
```

## Significado de indicadores

| Indicador | True | False |
|-----------|------|-------|
| `resolved_autonomously` | Bot respondió con contexto relevante | Respuesta es fallback o requiere agencia |
| `escalated_to_human` | Transferencia ejecutada a asesor | No hay transferencia |
| `needs_agency_confirmation` | Condición pendiente de confirmar | Información disponible |

**Importante**: `escalated_to_human` solo indica transferencia efectiva, no orientación como "contacta a la agencia".

## Limitaciones

- Precios son **estimaciones**, no tarifas oficiales
- Inclusiones son **escenarios simulados**
- Políticas de reserva/pago/cancelación **no confirmadas**
- No hay conexión a inventario real
- No hay sistema de derivación a asesores
- Detección de idioma: español, inglés, portugués, francés

## Evidencia de pruebas

- `evaluation-ten-local-*.json`: Resultados de evaluación local
- `INFORME_ANTES_DESPUES.md`: Comparativa de correcciones
- `REVISION_OPENCODE.md`: Revisión de cambios de OpenCode
- `test_four_fallos.py`: Prueba específica de fallos corregidos

## Revertir cambios

Si es necesario volver al estado anterior:
```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba
Copy-Item app_backup.ps1 app.py
Copy-Item trial_support_backup.ps1 trial_support.py
```

## Archivos principales

| Archivo | Función |
|---------|---------|
| `app.py` | Servidor FastAPI, cadena RAG, endpoints |
| `trial_support.py` | Adaptador para copia de prueba |
| `data/provisional.json` | Catálogo provisional de tours |
| `chroma_provisional_db/` | Base vectorial |
| `src/retriever.py` | Retriever híbrido BM25+Vectorial |

## Dependencias

- Python 3.11
- FastAPI, Uvicorn
- LangChain, ChromaDB
- HuggingFace Embeddings (offline)
- langdetect

## Soporte

Para problemas, consultar:
- `ESTADO_CIERRE.md`: Estado actual del proyecto
- `INFORME_ANTES_DESPUES.md`: Detalle de correcciones
- `REVISION_OPENCODE.md`: Revisión técnica
