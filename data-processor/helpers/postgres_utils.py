# Utilidades para PostgreSQL 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilidades para interactuar con PostgreSQL
"""

import os
import logging
import psycopg2
import pandas as pd

# Configurar logging
logger = logging.getLogger('postgres_utils')

# Constantes para conexión a PostgreSQL
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'ena_database')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'postgres')


def get_db_connection():
    """Establece y devuelve una conexión a la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Error al conectar a PostgreSQL: {e}")
        raise


def execute_query(query, params=None):
    """Ejecuta una consulta SQL en PostgreSQL y devuelve los resultados"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, params or ())
        
        # Si es una consulta SELECT, devolver resultados
        if query.strip().upper().startswith('SELECT'):
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            
            # Convertir a DataFrame
            df = pd.DataFrame(results, columns=columns)
            
            cursor.close()
            conn.close()
            return df
        
        # Si es una consulta de modificación, hacer commit y devolver recuento
        else:
            conn.commit()
            row_count = cursor.rowcount
            
            cursor.close()
            conn.close()
            return row_count
    
    except Exception as e:
        logger.error(f"Error al ejecutar consulta SQL: {e}")
        logger.error(f"Consulta: {query}")
        if params:
            logger.error(f"Parámetros: {params}")
        raise


def bulk_insert(table_name, df, columns=None):
    """Inserta múltiples filas de un DataFrame en una tabla"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Si no se especifican columnas, usar todas las columnas del DataFrame
        if columns is None:
            columns = df.columns.tolist()
        
        # Crear la consulta SQL para la inserción
        column_str = ', '.join(columns)
        value_placeholders = ', '.join(['%s'] * len(columns))
        query = f"INSERT INTO {table_name} ({column_str}) VALUES ({value_placeholders})"
        
        # Preparar los valores para la inserción masiva
        values = [tuple(row) for row in df[columns].values]
        
        # Ejecutar la inserción masiva
        cursor.executemany(query, values)
        
        # Commit y cerrar
        conn.commit()
        row_count = cursor.rowcount
        
        cursor.close()
        conn.close()
        
        logger.info(f"Insertadas {row_count} filas en {table_name}")
        return row_count
    
    except Exception as e:
        logger.error(f"Error en inserción masiva: {e}")
        logger.error(f"Tabla: {table_name}")
        logger.error(f"Columnas: {columns}")
        raise


def get_dimension_id(dimension_table, column_name, column_value):
    """Obtiene el ID de una dimensión basado en un valor de columna"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Consultar el ID
        query = f"SELECT id_{dimension_table.replace('dim_', '')} FROM {dimension_table} WHERE {column_name} = %s"
        cursor.execute(query, (column_value,))
        
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        else:
            logger.warning(f"No se encontró ID en {dimension_table} para {column_name}={column_value}")
            return None
    
    except Exception as e:
        logger.error(f"Error al obtener ID de dimensión: {e}")
        raise