"""Configuración base para el directorio de pruebas (tests).
Asegura que el directorio raíz del proyecto esté en sys.path.
"""
import os
import sys
from pathlib import Path

# Agregar la raíz del proyecto activo al sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
