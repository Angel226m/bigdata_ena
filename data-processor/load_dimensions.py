# Script para cargar dimensiones 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para cargar tablas dimensionales de la ENA 2021
Este script procesa los archivos CSV y carga las tablas dimensionales en PostgreSQL
"""

import os
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


def load_dim_ubicacion():
    """Carga la dimensión de ubicación geográfica"""
    logger.info("Cargando dimensión de ubicación...")
    
    try:
        # Leer datos de ubicación de cualquier archivo con estructura común
        files = [
            "Cap100_1 ENA 2021.csv",
            "Cap200a ENA 2021.csv",
            "Cap400a_1 ENA 2021.csv"
        ]
        
        # Intentar abrir archivos hasta encontrar uno disponible
        df = None
        for file in files:
            file_path = os.path.join(DATA_DIR, file)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path, low_memory=False)
                logger.info(f"Usando {file} para datos de ubicación")
                break
        
        if df is None:
            logger.error("No se encontró ningún archivo para cargar datos de ubicación")
            return
        
        # Seleccionar columnas geográficas y eliminar duplicados
        ubicacion_cols = ['CCDD', 'NOMBREDD', 'CCPP', 'NOMBREPV', 'CCDI', 'NOMBREDI', 'REGION', 'DOMINIO']
        dim_ubicacion = df[ubicacion_cols].drop_duplicates()
        
        # Renombrar columnas para coincidencia con base de datos
        dim_ubicacion.columns = ['ccdd', 'nombredd', 'ccpp', 'nombrepv', 'ccdi', 'nombredi', 'region', 'dominio']
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar registros
        for _, row in dim_ubicacion.iterrows():
            cursor.execute("""
                INSERT INTO dim_ubicacion 
                (ccdd, nombredd, ccpp, nombrepv, ccdi, nombredi, region, dominio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ccdd, ccpp, ccdi) DO NOTHING
            """, (
                row['ccdd'], row['nombredd'], row['ccpp'], row['nombrepv'],
                row['ccdi'], row['nombredi'], row['region'], row['dominio']
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión ubicación cargada: {len(dim_ubicacion)} registros")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión ubicación: {e}")
        raise


def load_dim_productor():
    """Carga la dimensión de productor"""
    logger.info("Cargando dimensión de productor...")
    
    try:
        # Leer datos de productor
        file_path = os.path.join(DATA_DIR, "Cap100_1 ENA 2021.csv")
        if not os.path.exists(file_path):
            logger.error(f"No se encontró el archivo {file_path}")
            return
        
        df_productor = pd.read_csv(file_path, low_memory=False)
        
        # Intentar cargar datos adicionales del Cap1100
        file_path_1100 = os.path.join(DATA_DIR, "Cap1100 ENA 2021.csv")
        df_1100 = None
        if os.path.exists(file_path_1100):
            df_1100 = pd.read_csv(file_path_1100, low_memory=False)
            logger.info("Datos adicionales de Cap1100 cargados")
        
        # Seleccionar columnas del productor y eliminar duplicados
        productor_cols = ['CODIGO', 'P102_1', 'P102_2', 'P105_N']
        dim_productor = df_productor[productor_cols].drop_duplicates()
        
        # Renombrar columnas para coincidencia con base de datos
        dim_productor.columns = ['codigo', 'tipo_productor', 'condicion_juridica', 'nivel_educativo']
        
        # Agregar columnas adicionales si se tienen datos de Cap1100
        if df_1100 is not None:
            # Seleccionar columnas relevantes y fusionar
            try:
                cols_1100 = ['CODIGO', 'P1102', 'P1103']  # Sexo y Edad, ajustar según estructura real
                df_1100_subset = df_1100[cols_1100].drop_duplicates()
                df_1100_subset.columns = ['codigo', 'sexo', 'edad']
                
                # Fusionar datos
                dim_productor = dim_productor.merge(
                    df_1100_subset, 
                    on='codigo', 
                    how='left'
                )
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
        for _, row in dim_productor.iterrows():
            cursor.execute("""
                INSERT INTO dim_productor 
                (codigo, tipo_productor, condicion_juridica, nivel_educativo, sexo, edad, experiencia_agropecuaria)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (
                row['codigo'], row['tipo_productor'], row['condicion_juridica'], row['nivel_educativo'],
                row['sexo'], row['edad'], row['experiencia_agropecuaria']
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión productor cargada: {len(dim_productor)} registros")
    
    except Exception as e:
        logger.error(f"Error al cargar dimensión productor: {e}")
        raise


def load_dim_cultivo():
    """Carga la dimensión de cultivo"""
    logger.info("Cargando dimensión de cultivo...")
    
    try:
        # Leer datos de cultivos
        file_path = os.path.join(DATA_DIR, "Cap200a ENA 2021.csv")
        if not os.path.exists(file_path):
            logger.error(f"No se encontró el archivo {file_path}")
            return
        
        df_cultivo = pd.read_csv(file_path, low_memory=False)
        
        # Seleccionar columnas del cultivo y eliminar duplicados
        cultivo_cols = ['P204_COD', 'P204_NOM', 'P204_TIPO']
        dim_cultivo = df_cultivo[cultivo_cols].drop_duplicates()
        
        # Renombrar columnas para coincidencia con base de datos
        dim_cultivo.columns = ['codigo', 'nombre', 'tipo']
        
        # Conectar a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insertar registros
        for _, row in dim_cultivo.iterrows():
            cursor.execute("""
                INSERT INTO dim_cultivo 
                (codigo, nombre, tipo)
                VALUES (%s, %s, %s)
                ON CONFLICT (codigo) DO NOTHING
            """, (
                row['codigo'], row['nombre'], row['tipo']
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión cultivo cargada: {len(dim_cultivo)} registros")
    
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
            cursor.execute("""
                INSERT INTO dim_tiempo 
                (anio, trimestre, mes)
                VALUES (%s, %s, %s)
                ON CONFLICT (anio, trimestre, mes) DO NOTHING
            """, (2021, trimestre, 0))
        
        # También insertar un registro anual (trimestre 0)
        cursor.execute("""
            INSERT INTO dim_tiempo 
            (anio, trimestre, mes)
            VALUES (%s, %s, %s)
            ON CONFLICT (anio, trimestre, mes) DO NOTHING
        """, (2021, 0, 0))
        
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
        
        for usa_fertilizantes, analisis_suelo, riego_tecnificado, conservacion_suelos, asistencia_tecnica in tecnologias:
            cursor.execute("""
                INSERT INTO dim_tecnologia 
                (usa_fertilizantes, analisis_suelo, riego_tecnificado, conservacion_suelos, asistencia_tecnica)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                usa_fertilizantes, analisis_suelo, riego_tecnificado, 
                conservacion_suelos, asistencia_tecnica
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Dimensión tecnología cargada: {len(tecnologias)} registros")
    
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