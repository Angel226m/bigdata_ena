#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('file_checker')

DATA_DIR = '/data'

def list_csv_files():
    """Lista todos los archivos CSV en el directorio de datos"""
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    logger.info(f"Se encontraron {len(csv_files)} archivos CSV:")
    
    for file in sorted(csv_files):
        logger.info(f" - {os.path.basename(file)}")
    
    return csv_files

def check_required_files():
    """Verifica si los archivos requeridos existen"""
    required_files = [
        "Cap100_1 ENA 2021.csv",
        "Cap200a ENA 2021.csv",
        "Cap400a_1 ENA 2021.csv",
        "Cap500ab ENA 2021.csv",
        "Cap700 ENA 2021.csv",
        "Cap800 ENA 2021.csv"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(os.path.join(DATA_DIR, file)):
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"Faltan {len(missing_files)} archivos requeridos:")
        for file in missing_files:
            logger.error(f" - {file}")
    else:
        logger.info("Todos los archivos requeridos están presentes.")
    
    return missing_files

if __name__ == "__main__":
    logger.info("Verificando archivos CSV en el directorio de datos...")
    csv_files = list_csv_files()
    missing_files = check_required_files()