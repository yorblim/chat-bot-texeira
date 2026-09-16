# Instrucciones de Reversion

**Objetivo**: Revertir los cambios al version original si es necesario.

---

## 1. Reversion rapida (recomendada)

```bash
cd C:\Users\HP\Desktop\Chat bot\texeira-prueba

# Copiar backups originales
Copy-Item app_backup.ps1 app.py -Force
Copy-Item trial_support_backup.ps1 trial_support.py -Force

# Eliminar cache
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue

# Reiniciar servidor
.\INICIAR.ps1
```

---

## 2. Reversion selectiva

Si solo quiere revertir algunos cambios:

### 2.1 Revertir solo needs_escalation
Copiar lineas 568-608 de `app_backup.ps1` a `app.py`

### 2.2 Revertir solo post-procesamiento
Copiar lineas 968-982 de `app_backup.ps1` a `app.py`

### 2.3 Revertir solo historial
Copiar lineas 990-997 de `app_backup.ps1` a `app.py`

### 2.4 Revertir solo ruta determinista
Copiar lineas 139-152 de `trial_support_backup.ps1` a `trial_support.py`

---

## 3. Verificar reversion

```bash
python test_trial.py
```

Si pasa, la reversion fue exitosa.

---

## 4. Archivos de respaldo

| Archivo | Version |
|---------|---------|
| app_backup.ps1 | Original (antes de correcciones) |
| trial_support_backup.ps1 | Original (antes de correcciones) |
| app_final.ps1 | Version corregida |
| trial_support_final.ps1 | Version corregida |

---

## 5. Notas importantes

- **NO** modificar `texeira-chatbot/` (proyecto original)
- **NO** ejecutar sin backup
- **NO** integrar sin autorizacion
- Los cambios son solo para `texeira-prueba/`
