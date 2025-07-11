#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import pandas as pd
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('file_checker')

DATA_DIR = '/data'

def list_csv_files():
    """Lista todos los archivos CSV en el directorio de datos"""
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    logger.info(f"Se encontraron {len(csv_files)} archivos CSV:")
    
    for file in sorted(csv_files):
        logger.info(f" - {os.path.basename(file)}")
        
        # Mostrar las primeras columnas de cada archivo
        try:
            df = pd.read_csv(file, nrows=1)
            logger.info(f"   Columnas: {', '.join(df.columns[:10])}{'...' if len(df.columns) > 10 else ''}")
        except Exception as e:
            logger.error(f"   Error al leer el archivo: {e}")
    
    return csv_files

def map_files_to_chapters():
    """Mapea los archivos encontrados a los capítulos de la ENA"""
    csv_files = list_csv_files()
    chapter_mapping = {}
    
    # Patrones para buscar archivos de cada capítulo
    patterns = {
        "Cap100_1": ["cap100_1", "100_1"],
        "Cap100_2": ["cap100_2", "100_2"],
        "Cap200a": ["cap200a", "200a"],
        "Cap200ab": ["cap200ab", "200ab"],
        "Cap200c": ["cap200c", "200c"],
        "Cap200d": ["cap200d", "200d"],
        "Cap200e": ["cap200e", "200e"],
        "Cap300ab": ["cap300ab", "300ab"],
        "Cap400a_1": ["cap400a_1", "400a_1"],
        "Cap400a_2": ["cap400a_2", "400a_2"],
        "Cap400b": ["cap400b", "400b"],
        "Cap400c": ["cap400c", "400c"],
        "Cap500ab": ["cap500ab", "500ab"],
        "Cap700": ["cap700", "700"],
        "Cap800": ["cap800", "800"],
        "Cap1000": ["cap1000", "1000"],
        "Cap1100": ["cap1100", "1100"],
        "Cap1200": ["cap1200", "1200"],
        "Cap1200a": ["cap1200a", "1200a"],
        "Cap1200b": ["cap1200b", "1200b"],
        "Cap1200c": ["cap1200c", "1200c"]
    }
    
    # Mapear archivos a capítulos
    for chapter, patterns_list in patterns.items():
        for file in csv_files:
            basename = os.path.basename(file).lower()
            if any(pattern.lower() in basename for pattern in patterns_list):
                chapter_mapping[chapter] = file
                break
    
    # Mostrar mapeo
    logger.info("Mapeo de archivos a capítulos:")
    for chapter, file in chapter_mapping.items():
        logger.info(f" - {chapter}: {os.path.basename(file)}")
    
    # Verificar capítulos faltantes
    all_chapters = set(patterns.keys())
    found_chapters = set(chapter_mapping.keys())
    missing_chapters = all_chapters - found_chapters
    
    if missing_chapters:
        logger.warning("Capítulos sin archivos correspondientes:")
        for chapter in missing_chapters:
            logger.warning(f" - {chapter}")
    
    return chapter_mapping

if __name__ == "__main__":
    logger.info("Verificando archivos CSV en el directorio de datos...")
    files = list_csv_files()
    chapter_mapping = map_files_to_chapters()
    
    logger.info("Verificación completada.")
    if files:
        logger.info(f"Total de archivos CSV encontrados: {len(files)}")
    else:
        logger.error("No se encontraron archivos CSV en el directorio de datos.")