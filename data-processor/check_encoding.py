#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para verificar y detectar la codificación de los archivos CSV
"""

import os
import glob
import chardet
import pandas as pd
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('encoding_checker')

DATA_DIR = '/data'

def detect_encoding(file_path):
    """Detecta la codificación de un archivo"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(100000)  # Leer los primeros 100KB para detectar la codificación
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        confidence = result['confidence']
        logger.info(f"Archivo {os.path.basename(file_path)}: Codificación detectada = {encoding} (confianza: {confidence:.2f})")
        return encoding

def test_read_csv(file_path, encoding=None):
    """Intenta leer un archivo CSV con la codificación especificada"""
    encodings_to_try = ['utf-8', 'latin-1', 'ISO-8859-1', 'windows-1252', 'cp1252']
    
    if encoding:
        encodings_to_try.insert(0, encoding)
    
    for enc in encodings_to_try:
        try:
            logger.info(f"Intentando leer {os.path.basename(file_path)} con codificación {enc}")
            df = pd.read_csv(file_path, encoding=enc, nrows=5)
            logger.info(f"✅ Lectura exitosa con codificación {enc}")
            logger.info(f"Primeras columnas: {', '.join(df.columns[:5])}")
            return enc
        except UnicodeDecodeError:
            logger.warning(f"❌ Error de decodificación con {enc}")
        except Exception as e:
            logger.error(f"❌ Error al leer el archivo: {e}")
    
    logger.error(f"❌ No se pudo leer el archivo {os.path.basename(file_path)} con ninguna codificación")
    return None

def check_all_files():
    """Verifica la codificación de todos los archivos CSV en el directorio de datos"""
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    logger.info(f"Se encontraron {len(csv_files)} archivos CSV")
    
    results = {}
    
    for file in csv_files:
        try:
            detected_encoding = detect_encoding(file)
            working_encoding = test_read_csv(file, detected_encoding)
            results[os.path.basename(file)] = working_encoding
        except Exception as e:
            logger.error(f"Error al procesar {os.path.basename(file)}: {e}")
            results[os.path.basename(file)] = None
    
    # Mostrar resumen
    logger.info("\n=== RESUMEN DE CODIFICACIONES ===")
    for file, encoding in results.items():
        status = "✅ OK" if encoding else "❌ ERROR"
        logger.info(f"{status} - {file}: {encoding or 'No se pudo determinar'}")
    
    # Guardar configuración
    with open('/app/file_encodings.py', 'w') as f:
        f.write("# Codificaciones detectadas para los archivos CSV\n\n")
        f.write("FILE_ENCODINGS = {\n")
        for file, encoding in results.items():
            f.write(f"    '{file}': '{encoding or 'latin-1'}',\n")
        f.write("}\n")
    
    logger.info("Configuración de codificaciones guardada en /app/file_encodings.py")

if __name__ == "__main__":
    logger.info("Verificando codificación de archivos CSV...")
    check_all_files()