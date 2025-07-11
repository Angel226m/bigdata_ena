#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para ejecutar la versión corregida de carga de dimensiones
"""

import logging
from fixed_load_dimensions import load_all_dimensions

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('fixed_load')

if __name__ == "__main__":
    logger.info("Ejecutando versión corregida de carga de dimensiones...")
    load_all_dimensions()
    logger.info("Proceso completado.")