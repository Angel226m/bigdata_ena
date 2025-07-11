#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script modificado para cargar tablas dimensionales de la ENA 2021
- Corrige problemas de codificación en la lectura de archivos CSV
"""

import os
import glob
import pandas as pd
import logging
from helpers.postgres_utils import get_db_connection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('load_dimensions')

# Constantes
DATA_DIR = '/data'

def find_file_by_pattern(pattern):
    """Busca un archivo que coincida con el patrón especificado"""
    files = glob.glob(os.path.join(DATA_DIR, f"*{pattern}*.csv"))
    if files:
        logger.info(f"Archivo encontrado para patrón '{pattern}': {os.path.basename(files[0])}")
        return files[0]
    else:
        logger.error(f"No se encontró ningún archivo para el patrón '{pattern}'")
        return None

def read_csv_safely(file_path, **kwargs):
    """Lee un archivo CSV probando diferentes codificaciones"""
    encodings = ['latin-1', 'cp1252', 'ISO-8859-1', 'windows-1252', 'utf-8']
    
    for encoding in encodings:
        try:
            logger.info(f"Intentando leer {os.path.basename(file_path)} con codificación {encoding}")
            df = pd.read_csv(file_path, encoding=encoding, **kwargs)
            logger.info(f"✅ Archivo {os.path.basename(file_path)} leído correctamente con codificación {encoding}")
            return df
        except UnicodeDecodeError:
            logger.warning(f"❌ Error de decodificación con {encoding}")
        except Exception as e:
            logger.error(f"❌ Error al leer el archivo: {e}")
    
    # Si todas las codificaciones fallan, intentar con engine='python' que es más tolerante
    try:
        logger.info(f"Intentando leer con engine='python'...")
        df = pd.read_csv(file_path, encoding='latin-1', engine='python', **kwargs)
        logger.info("✅ Lectura exitosa con engine='python'")
        return df
    except Exception as e:
        logger.error(f"❌ No se pudo leer el archivo con ninguna codificación: {e}")
        raise

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
            
        # Leer archivo encontrado
        df = read_csv_safely(file_path, low_memory=False)
        logger.info(f"Usando {os.path.basename(file_path)} para datos de ubicación")
        
        # Verificar las columnas disponibles
        print("Columnas disponibles en el archivo:", df.columns.tolist())
        
        # Mapear columnas necesarias
        column_mapping = {}
        for col in df.columns:
            if 'CCDD' in col:
                column_mapping['CCDD'] = col
            elif 'NOMBREDD' in col:
                column_mapping['NOMBREDD'] = col
            elif 'CCPP' in col:
                column_mapping['CCPP'] = col
            elif 'NOMBREPV' in col:
                column_mapping['NOMBREPV'] = col
            elif 'CCDI' in col:
                column_mapping['CCDI'] = col
            elif 'NOMBREDI' in col:
                column_mapping['NOMBREDI'] = col
            elif 'REGION' in col:
                column_mapping['REGION'] = col
            elif 'DOMINIO' in col:
                column_mapping['DOMINIO'] = col
        
        # Si no se encontraron suficientes columnas, usar nombres exactos
        if len(column_mapping) < 4:
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
                    str(row['ccdd']), str(row['nombredd']), str(row['ccpp']), str(row['nombrepv']),
                    str(row['ccdi']), str(row['nombredi']), str(row['region']), str(row['dominio'])
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
        
        # Leer con codificación segura
        df_productor = read_csv_safely(file_path, low_memory=False)
        
        # Buscar archivo con datos adicionales (Cap1100)
        file_path_1100 = find_file_by_pattern("Cap1100")
        df_1100 = None
        if file_path_1100:
            try:
                df_1100 = read_csv_safely(file_path_1100, low_memory=False)
                logger.info("Datos adicionales de Cap1100 cargados")
            except Exception as e:
                logger.warning(f"No se pudieron cargar datos de Cap1100: {e}")
                df_1100 = None
        
        # Verificar columnas disponibles
        print("Columnas disponibles en Cap100_1:", df_productor.columns.tolist())
        
        # Mapear columnas
        column_mapping = {}
        for col in df_productor.columns:
            if col == 'CODIGO':
                column_mapping['CODIGO'] = col
            elif 'P102_1' in col:
                column_mapping['P102_1'] = col
            elif 'P102_2' in col:
                column_mapping['P102_2'] = col
            elif 'P105_N' in col:
                column_mapping['P105_N'] = col
        
        # Si no se encontraron suficientes columnas, usar nombres exactos
        if len(column_mapping) < 2:
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
                    str(row['codigo']), 
                    str(row['tipo_productor']), 
                    str(row['condicion_juridica']), 
                    str(row['nivel_educativo']),
                    str(row['sexo']) if row['sexo'] is not None else None, 
                    int(row['edad']) if row['edad'] is not None and pd.notna(row['edad']) else None, 
                    int(row['experiencia_agropecuaria']) if row['experiencia_agropecuaria'] is not None and pd.notna(row['experiencia_agropecuaria']) else None
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
            file_path = find_file_by_pattern("Cap200ab")
            if not file_path:
                logger.error("No se encontró ningún archivo para Cap200a o Cap200ab")
                return
        
        # Leer con codificación segura
        df_cultivo = read_csv_safely(file_path, low_memory=False)
        
        # Verificar columnas disponibles
        print("Columnas disponibles en Cap200a:", df_cultivo.columns.tolist())
        
        # Mapear columnas necesarias
        column_mapping = {}
        for col in df_cultivo.columns:
            if 'P204_COD' in col:
                column_mapping['P204_COD'] = col
            elif 'P204_NOM' in col:
                column_mapping['P204_NOM'] = col
            elif 'P204_TIPO' in col:
                column_mapping['P204_TIPO'] = col
        
        # Si no se encontraron suficientes columnas, usar nombres exactos
        if len(column_mapping) < 2:
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
                    str(row['codigo']), 
                    str(row['nombre']), 
                    str(row['tipo'])
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