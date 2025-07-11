#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script modificado para cargar tablas dimensionales de la ENA 2021
adaptado para trabajar con los nombres de archivo del formato: 01_Cap100_1_0.csv
y diferentes codificaciones de caracteres
"""

import os
import glob
import pandas as pd
import logging
import chardet
from helpers.postgres_utils import get_db_connection

# Intentar importar codificaciones de archivo si existe
try:
    from file_encodings import FILE_ENCODINGS
except ImportError:
    FILE_ENCODINGS = {}

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('load_dimensions')

# Constantes
DATA_DIR = '/data'

def detect_encoding(file_path):
    """Detecta la codificación de un archivo"""
    basename = os.path.basename(file_path)
    
    # Usar codificación predeterminada si está disponible
    if basename in FILE_ENCODINGS and FILE_ENCODINGS[basename]:
        return FILE_ENCODINGS[basename]
    
    # Detectar codificación
    with open(file_path, 'rb') as f:
        raw_data = f.read(100000)  # Leer los primeros 100KB para detectar la codificación
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        return encoding or 'latin-1'

def read_csv_with_encoding(file_path):
    """Lee un archivo CSV con la codificación adecuada"""
    basename = os.path.basename(file_path)
    
    # Lista de codificaciones para intentar
    encodings_to_try = ['utf-8', 'latin-1', 'ISO-8859-1', 'windows-1252', 'cp1252']
    
    # Detectar codificación y ponerla primero en la lista
    detected_encoding = detect_encoding(file_path)
    if detected_encoding:
        encodings_to_try.insert(0, detected_encoding)
    
    # Intentar leer con diferentes codificaciones
    for encoding in encodings_to_try:
        try:
            logger.info(f"Intentando leer {basename} con codificación {encoding}")
            df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
            logger.info(f"✅ Archivo {basename} leído correctamente con codificación {encoding}")
            return df
        except UnicodeDecodeError:
            logger.warning(f"❌ Error de decodificación con {encoding}")
        except Exception as e:
            logger.error(f"❌ Error al leer el archivo: {e}")
    
    # Si ninguna codificación funciona, intentar sin especificar codificación
    try:
        df = pd.read_csv(file_path, low_memory=False)
        logger.info(f"✅ Archivo {basename} leído correctamente con codificación por defecto")
        return df
    except Exception as e:
        logger.error(f"❌ No se pudo leer el archivo {basename} con ninguna codificación: {e}")
        raise

def find_file_by_pattern(pattern):
    """Busca un archivo que coincida con el patrón especificado"""
    files = glob.glob(os.path.join(DATA_DIR, f"*{pattern}*.csv"))
    if files:
        logger.info(f"Archivo encontrado para patrón '{pattern}': {os.path.basename(files[0])}")
        return files[0]
    else:
        logger.error(f"No se encontró ningún archivo para el patrón '{pattern}'")
        return None

def load_dim_ubicacion():
    """Carga la dimensión de ubicación geográfica"""
    logger.info("Cargando dimensión de ubicación...")
    
    try:
        # Buscar archivos que contengan información geográfica
        file_path = find_file_by_pattern("Cap100_1")
        
        if not file_path:
            # Intentar con otro archivo
            file_path = find_file_by_pattern("Cap200a")
            
        if not file_path:
            # Intentar con otro archivo más
            file_path = find_file_by_pattern("Cap400a_1")
            
        if not file_path:
            logger.error("No se encontró ningún archivo para cargar datos de ubicación")
            return
            
        # Leer archivo encontrado con la codificación adecuada
        df = read_csv_with_encoding(file_path)
        logger.info(f"Usando {os.path.basename(file_path)} para datos de ubicación")
        
        # Verificar las columnas disponibles
        print("Columnas disponibles en el archivo:", df.columns.tolist())
        
        # Definir mapeo de columnas estándar a las columnas reales
        # Ajustar estos nombres según las columnas reales en tus CSV
        column_mapping = {
            'CCDD': 'CCDD', 
            'NOMBREDD': 'NOMBREDD',
            'CCPP': 'CCPP', 
            'NOMBREPV': 'NOMBREPV',
            'CCDI': 'CCDI', 
            'NOMBREDI': 'NOMBREDI',
            'REGION': 'REGION',
            'DOMINIO': 'DOMINIO'
        }
        
        # Verificar qué columnas están disponibles realmente
        available_columns = []
        renamed_columns = []
        
        for expected, actual in column_mapping.items():
            if actual in df.columns:
                available_columns.append(actual)
                renamed_columns.append(expected)
                
        # Si faltan columnas esenciales, intentar inferirlas o usar valores predeterminados
        if len(available_columns) < 2:
            logger.error(f"No hay suficientes columnas de ubicación en {os.path.basename(file_path)}")
            return
            
        # Seleccionar columnas disponibles y eliminar duplicados
        dim_ubicacion = df[available_columns].drop_duplicates()
        dim_ubicacion.columns = renamed_columns
        
        # Completar columnas faltantes con valores predeterminados
        all_expected = ['CCDD', 'NOMBREDD', 'CCPP', 'NOMBREPV', 'CCDI', 'NOMBREDI', 'REGION', 'DOMINIO']
        for col in all_expected:
            if col not in renamed_columns:
                dim_ubicacion[col] = 'ND'  # ND = No Disponible
        
        # Renombrar columnas para coincidencia con base de datos
        dim_ubicacion.columns = ['ccdd', 'nombredd', 'ccpp', 'nombrepv', 'ccdi', 'nombredi', 'region', 'dominio']
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar registros
        inserted = 0
        for _, row in dim_ubicacion.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO dim_ubicacion 
                    (ccdd, nombredd, ccpp, nombrepv, ccdi, nombredi, region, dominio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ccdd, ccpp, ccdi) DO NOTHING
                """, (
                    row['ccdd'], row['nombredd'], row['ccpp'], row['nombrepv'],
                    row['ccdi'], row['nombredi'], row['region'], row['dominio']
                ))
                inserted += 1
            except Exception as e:
                logger.error(f"Error al insertar registro: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión ubicación cargada: {inserted} registros")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión ubicación: {e}")
        raise


def load_dim_productor():
    """Carga la dimensión de productor"""
    logger.info("Cargando dimensión de productor...")
    
    try:
        # Buscar archivo de productor
        file_path = find_file_by_pattern("Cap100_1")
        if not file_path:
            logger.error("No se encontró ningún archivo para Cap100_1")
            return
        
        df_productor = pd.read_csv(file_path, low_memory=False)
        
        # Buscar archivo con datos adicionales (Cap1100)
        file_path_1100 = find_file_by_pattern("Cap1100")
        df_1100 = None
        if file_path_1100:
            df_1100 = pd.read_csv(file_path_1100, low_memory=False)
            logger.info("Datos adicionales de Cap1100 cargados")
        
        # Verificar columnas disponibles
        print("Columnas disponibles en Cap100_1:", df_productor.columns.tolist())
        
        # Mapear columnas - ajusta estos nombres según los reales en tu CSV
        column_mapping = {
            'CODIGO': 'CODIGO',
            'P102_1': 'P102_1', 
            'P102_2': 'P102_2', 
            'P105_N': 'P105_N'
        }
        
        # Verificar qué columnas están disponibles
        available_columns = []
        renamed_columns = []
        
        for expected, actual in column_mapping.items():
            if actual in df_productor.columns:
                available_columns.append(actual)
                renamed_columns.append(expected)
                
        # Si no hay columnas suficientes, salir
        if 'CODIGO' not in renamed_columns or len(available_columns) < 2:
            logger.error(f"No hay suficientes columnas de productor en {os.path.basename(file_path)}")
            return
            
        # Seleccionar columnas del productor y eliminar duplicados
        dim_productor = df_productor[available_columns].drop_duplicates()
        dim_productor.columns = renamed_columns
        
        # Rellenar columnas faltantes
        all_expected = ['CODIGO', 'P102_1', 'P102_2', 'P105_N']
        for col in all_expected:
            if col not in renamed_columns:
                dim_productor[col] = 'ND'  # ND = No Disponible
        
        # Renombrar columnas para coincidencia con base de datos
        dim_productor.columns = ['codigo', 'tipo_productor', 'condicion_juridica', 'nivel_educativo']
        
        # Agregar columnas adicionales si se tienen datos de Cap1100
        if df_1100 is not None:
            # Seleccionar columnas relevantes y fusionar
            try:
                # Verificar columnas disponibles
                print("Columnas disponibles en Cap1100:", df_1100.columns.tolist())
                
                # Mapear columnas - ajusta estos nombres según los reales en tu CSV
                cols_1100_map = {
                    'CODIGO': 'CODIGO',
                    'P1102': 'P1102',  # Sexo
                    'P1103': 'P1103'   # Edad
                }
                
                available_cols_1100 = []
                renamed_cols_1100 = []
                
                for expected, actual in cols_1100_map.items():
                    if actual in df_1100.columns:
                        available_cols_1100.append(actual)
                        renamed_cols_1100.append(expected)
                
                if 'CODIGO' in renamed_cols_1100 and len(available_cols_1100) > 1:
                    df_1100_subset = df_1100[available_cols_1100].drop_duplicates()
                    df_1100_subset.columns = renamed_cols_1100
                    
                    # Renombrar para la fusión
                    cols_to_rename = {
                        'P1102': 'sexo',
                        'P1103': 'edad'
                    }
                    
                    # Renombrar solo las columnas disponibles
                    for old_col, new_col in cols_to_rename.items():
                        if old_col in df_1100_subset.columns:
                            df_1100_subset.rename(columns={old_col: new_col}, inplace=True)
                    
                    # Fusionar datos
                    dim_productor = dim_productor.merge(
                        df_1100_subset[['CODIGO'] + [col for col in ['sexo', 'edad'] if col in df_1100_subset.columns]], 
                        left_on='codigo', 
                        right_on='CODIGO',
                        how='left'
                    )
                    
                    # Eliminar columna duplicada de CODIGO si existe
                    if 'CODIGO' in dim_productor.columns:
                        dim_productor.drop('CODIGO', axis=1, inplace=True)
            except Exception as e:
                logger.warning(f"No se pudieron incorporar datos de Cap1100: {e}")
        
        # Si no se tienen columnas adicionales, agregar con valores predeterminados
        if 'sexo' not in dim_productor.columns:
            dim_productor['sexo'] = None
        if 'edad' not in dim_productor.columns:
            dim_productor['edad'] = None
        if 'experiencia_agropecuaria' not in dim_productor.columns:
            dim_productor['experiencia_agropecuaria'] = None
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar registros
        inserted = 0
        for _, row in dim_productor.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO dim_productor 
                    (codigo, tipo_productor, condicion_juridica, nivel_educativo, sexo, edad, experiencia_agropecuaria)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (codigo) DO NOTHING
                """, (
                    row['codigo'], row['tipo_productor'], row['condicion_juridica'], row['nivel_educativo'],
                    row['sexo'], row['edad'], row['experiencia_agropecuaria']
                ))
                inserted += 1
            except Exception as e:
                logger.error(f"Error al insertar registro: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión productor cargada: {inserted} registros")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión productor: {e}")
        raise

def load_dim_cultivo():
    """Carga la dimensión de cultivo"""
    logger.info("Cargando dimensión de cultivo...")
    
    try:
        # Buscar archivo de cultivos
        file_path = find_file_by_pattern("Cap200a")
        if not file_path:
            logger.error("No se encontró ningún archivo para Cap200a")
            return
        
        df_cultivo = pd.read_csv(file_path, low_memory=False)
        
        # Verificar columnas disponibles
        print("Columnas disponibles en Cap200a:", df_cultivo.columns.tolist())
        
        # Mapear columnas - ajusta estos nombres según los reales en tu CSV
        column_mapping = {
            'P204_COD': 'P204_COD',
            'P204_NOM': 'P204_NOM', 
            'P204_TIPO': 'P204_TIPO'
        }
        
        # Verificar qué columnas están disponibles
        available_columns = []
        renamed_columns = []
        
        for expected, actual in column_mapping.items():
            if actual in df_cultivo.columns:
                available_columns.append(actual)
                renamed_columns.append(expected)
                
        # Si no hay columnas suficientes, salir
        if 'P204_COD' not in renamed_columns or len(available_columns) < 2:
            logger.error(f"No hay suficientes columnas de cultivo en {os.path.basename(file_path)}")
            return
            
        # Seleccionar columnas del cultivo y eliminar duplicados
        dim_cultivo = df_cultivo[available_columns].drop_duplicates()
        dim_cultivo.columns = renamed_columns
        
        # Rellenar columnas faltantes
        all_expected = ['P204_COD', 'P204_NOM', 'P204_TIPO']
        for col in all_expected:
            if col not in renamed_columns:
                dim_cultivo[col] = 'ND'  # ND = No Disponible
        
        # Renombrar columnas para coincidencia con base de datos
        dim_cultivo.columns = ['codigo', 'nombre', 'tipo']
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar registros
        inserted = 0
        for _, row in dim_cultivo.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO dim_cultivo 
                    (codigo, nombre, tipo)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (codigo) DO NOTHING
                """, (
                    row['codigo'], row['nombre'], row['tipo']
                ))
                inserted += 1
            except Exception as e:
                logger.error(f"Error al insertar registro: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión cultivo cargada: {inserted} registros")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión cultivo: {e}")
        raise

def load_dim_tiempo():
    """Carga la dimensión de tiempo"""
    logger.info("Cargando dimensión de tiempo...")
    
    try:
        # Para la dimensión tiempo, usamos el año fijo 2021 (ENA 2021)
        # y creamos registros para los 4 trimestres
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar registros para el año 2021, con 4 trimestres
        for trimestre in range(1, 5):
            try:
                cursor.execute("""
                    INSERT INTO dim_tiempo 
                    (anio, trimestre, mes)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (anio, trimestre, mes) DO NOTHING
                """, (2021, trimestre, 0))
            except Exception as e:
                logger.error(f"Error al insertar registro de tiempo: {e}")
                conn.rollback()
        
        # También insertar un registro anual (trimestre 0)
        try:
            cursor.execute("""
                INSERT INTO dim_tiempo 
                (anio, trimestre, mes)
                VALUES (%s, %s, %s)
                ON CONFLICT (anio, trimestre, mes) DO NOTHING
            """, (2021, 0, 0))
        except Exception as e:
            logger.error(f"Error al insertar registro de tiempo anual: {e}")
            conn.rollback()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Dimensión tiempo cargada: 5 registros (anual + 4 trimestres)")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión tiempo: {e}")
        raise

def load_dim_tecnologia():
    """Carga la dimensión de tecnología"""
    logger.info("Cargando dimensión de tecnología...")
    
    try:
        # Para la dimensión tecnología, creamos combinaciones predefinidas
        # de valores booleanos para las diferentes tecnologías
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar diferentes combinaciones de tecnologías
        tecnologias = [
            (True, True, True, True, True),    # Usa todas las tecnologías
            (True, True, True, False, True),   # No usa conservación de suelos
            (True, True, False, True, True),   # No usa riego tecnificado
            (True, False, True, True, True),   # No usa análisis de suelo
            (False, True, True, True, True),   # No usa fertilizantes
            (True, True, False, False, True),  # No usa riego ni conservación
            (True, False, False, True, True),  # No usa análisis ni riego
            (False, False, True, True, True),  # No usa fertilizantes ni análisis
            (False, False, False, False, False) # No usa ninguna tecnología
        ]
        
        inserted = 0
        for usa_fertilizantes, analisis_suelo, riego_tecnificado, conservacion_suelos, asistencia_tecnica in tecnologias:
            try:
                cursor.execute("""
                    INSERT INTO dim_tecnologia 
                    (usa_fertilizantes, analisis_suelo, riego_tecnificado, conservacion_suelos, asistencia_tecnica)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    usa_fertilizantes, analisis_suelo, riego_tecnificado, 
                    conservacion_suelos, asistencia_tecnica
                ))
                inserted += 1
            except Exception as e:
                logger.error(f"Error al insertar registro de tecnología: {e}")
                conn.rollback()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión tecnología cargada: {inserted} registros")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión tecnología: {e}")
        raise

def load_all_dimensions():
    """Carga todas las tablas dimensionales"""
    logger.info("Iniciando carga de todas las dimensiones...")
    
    load_dim_ubicacion()
    load_dim_productor()
    load_dim_cultivo()
    load_dim_tiempo()
    load_dim_tecnologia()
    
    logger.info("Carga de dimensiones completada")


if __name__ == "__main__":
    load_all_dimensions()