#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal para procesamiento de datos de la ENA 2021
Adaptado para trabajar con nombres de archivos en formato: 01_Cap100_1_0.csv
"""

import os
import glob
import time
import pandas as pd
import logging
from datetime import datetime

# Importar módulos auxiliares
from helpers.kafka_utils import create_producer, publish_message
from helpers.postgres_utils import get_db_connection
from load_dimensions import load_all_dimensions, find_file_by_pattern

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ena_processor')

# Constantes
DATA_DIR = '/data'
KAFKA_TOPIC_AGRICOLA = 'ena-agricola'
KAFKA_TOPIC_PECUARIA = 'ena-pecuaria'
KAFKA_TOPIC_SERVICIOS = 'ena-servicios'
KAFKA_TOPIC_RIEGO = 'ena-riego'

def list_csv_files():
    """Lista todos los archivos CSV en el directorio de datos"""
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    logger.info(f"Se encontraron {len(csv_files)} archivos CSV")
    return csv_files

def process_cap200_data(producer):
    """Procesa datos del capítulo 200 (Producción Agrícola)"""
    logger.info("Procesando datos del capítulo 200 (Producción Agrícola)...")
    
    # Cargar archivos relacionados
    try:
        # Buscar archivos por patrón
        file_200a = find_file_by_pattern("Cap200a")
        file_200c = find_file_by_pattern("Cap200c")
        file_200d = find_file_by_pattern("Cap200d")
        file_200e = find_file_by_pattern("Cap200e")
        
        if not file_200a or not file_200c:
            logger.error("No se encontraron archivos esenciales del capítulo 200")
            return
            
        cap200a = pd.read_csv(file_200a, low_memory=False)
        cap200c = pd.read_csv(file_200c, low_memory=False)
        
        logger.info(f"Archivos cargados - {os.path.basename(file_200a)}: {len(cap200a)} registros, {os.path.basename(file_200c)}: {len(cap200c)} registros")
        
        # Mostrar las columnas disponibles
        print("Columnas en Cap200a:", cap200a.columns.tolist())
        print("Columnas en Cap200c:", cap200c.columns.tolist())
        
        # Identificar columnas clave para la unión
        join_columns = []
        for col in ['ANIO', 'CCDD', 'CCPP', 'CCDI', 'CONGLOMERADO', 'NSELUA', 'UA', 'CODIGO', 'P204_COD']:
            if col in cap200a.columns and col in cap200c.columns:
                join_columns.append(col)
        
        if not join_columns:
            logger.error("No se encontraron columnas comunes para unir los datos")
            return
            
        logger.info(f"Uniendo datos usando columnas: {join_columns}")
        
        # Procesar datos básicos
        base_agricola = cap200a.merge(
            cap200c, 
            on=join_columns,
            how='inner'
        )
        
        # Agregar datos de costos si está disponible el archivo
        if file_200e:
            cap200e = pd.read_csv(file_200e, low_memory=False)
            print("Columnas en Cap200e:", cap200e.columns.tolist())
            
            # Intentar unir con datos de costos
            try:
                base_agricola = base_agricola.merge(
                    cap200e,
                    on=join_columns,
                    how='left'
                )
            except Exception as e:
                logger.warning(f"No se pudieron unir datos de costos: {e}")
        
        # Agregar datos de destino de producción si está disponible el archivo
        if file_200d:
            cap200d = pd.read_csv(file_200d, low_memory=False)
            print("Columnas en Cap200d:", cap200d.columns.tolist())
            
            # Intentar unir con datos de destino
            try:
                base_agricola = base_agricola.merge(
                    cap200d,
                    on=join_columns,
                    how='left'
                )
            except Exception as e:
                logger.warning(f"No se pudieron unir datos de destino: {e}")
        
        # Identificar columnas de producción
        superficie_sembrada_col = next((col for col in cap200a.columns if 'P218A' in col), None)
        superficie_cosechada_col = next((col for col in cap200a.columns if 'P218B' in col), None)
        produccion_ent_col = next((col for col in cap200c.columns if 'PROD_CORTE_ENT' in col), None)
        produccion_dec_col = next((col for col in cap200c.columns if 'PROD_CORTE_DEC' in col), None)
        
        if not superficie_sembrada_col or not superficie_cosechada_col:
            logger.error("No se encontraron columnas de superficie sembrada/cosechada")
            return
            
        if not produccion_ent_col or not produccion_dec_col:
            logger.error("No se encontraron columnas de producción")
            return
            
        # Calcular producción total combinando parte entera y decimal
        base_agricola['PRODUCCION_TOTAL'] = base_agricola[produccion_ent_col].fillna(0) + \
                                           base_agricola[produccion_dec_col].fillna(0)
        
        # Calcular rendimiento (producción / superficie cosechada)
        base_agricola['RENDIMIENTO'] = base_agricola.apply(
            lambda x: x['PRODUCCION_TOTAL'] / x[superficie_cosechada_col] if x[superficie_cosechada_col] > 0 else 0, 
            axis=1
        )
        
        # Publicar datos en Kafka
        records_published = 0
        for _, row in base_agricola.iterrows():
            try:
                # Crear mensaje con los campos relevantes
                message = {
                    'ANIO': int(row['ANIO']) if 'ANIO' in row and pd.notna(row['ANIO']) else 2021,
                    'CCDD': str(row['CCDD']) if 'CCDD' in row else '',
                    'CCPP': str(row['CCPP']) if 'CCPP' in row else '',
                    'CCDI': str(row['CCDI']) if 'CCDI' in row else '',
                    'CONGLOMERADO': str(row['CONGLOMERADO']) if 'CONGLOMERADO' in row else '',
                    'NSELUA': str(row['NSELUA']) if 'NSELUA' in row else '',
                    'UA': str(row['UA']) if 'UA' in row else '',
                    'CODIGO': str(row['CODIGO']) if 'CODIGO' in row else '',
                    'P204_COD': str(row['P204_COD']) if 'P204_COD' in row else '',
                    'P204_NOM': str(row['P204_NOM']) if 'P204_NOM' in row else '',
                    'P204_TIPO': str(row['P204_TIPO']) if 'P204_TIPO' in row else '',
                    'SUPERFICIE_SEMBRADA': float(row[superficie_sembrada_col]) if pd.notna(row[superficie_sembrada_col]) else 0.0,
                    'SUPERFICIE_COSECHADA': float(row[superficie_cosechada_col]) if pd.notna(row[superficie_cosechada_col]) else 0.0,
                    'PRODUCCION_TOTAL': float(row['PRODUCCION_TOTAL']),
                    'RENDIMIENTO': float(row['RENDIMIENTO']),
                    'timestamp': datetime.now().isoformat()
                }
                
                # Publicar mensaje
                publish_message(producer, KAFKA_TOPIC_AGRICOLA, message)
                records_published += 1
                
                # Mostrar progreso cada 1000 registros
                if records_published % 1000 == 0:
                    logger.info(f"Progreso: {records_published} registros publicados")
                
            except Exception as e:
                logger.error(f"Error al publicar mensaje: {e}")
        
        logger.info(f"Se publicaron {records_published} registros en Kafka (tema: {KAFKA_TOPIC_AGRICOLA})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos del capítulo 200: {e}")
        raise

def process_cap400_data(producer):
    """Procesa datos del capítulo 400 (Producción Pecuaria)"""
    logger.info("Procesando datos del capítulo 400 (Producción Pecuaria)...")
    
    # Cargar archivos relacionados
    try:
        # Buscar archivos por patrón
        file_400a_1 = find_file_by_pattern("Cap400a_1")
        file_400a_2 = find_file_by_pattern("Cap400a_2")
        file_400c = find_file_by_pattern("Cap400c")
        
        if not file_400a_1:
            logger.error("No se encontró el archivo esencial Cap400a_1")
            return
            
        cap400a_1 = pd.read_csv(file_400a_1, low_memory=False)
        
        logger.info(f"Archivo cargado - {os.path.basename(file_400a_1)}: {len(cap400a_1)} registros")
        
        # Mostrar las columnas disponibles
        print("Columnas en Cap400a_1:", cap400a_1.columns.tolist())
        
        # Identificar columnas relevantes
        tipo_animal_col = next((col for col in cap400a_1.columns if 'ESPECIE' in col), None)
        cantidad_col = next((col for col in cap400a_1.columns if 'NRO' in col), None)
        
        if not tipo_animal_col or not cantidad_col:
            logger.error("No se encontraron columnas de tipo de animal o cantidad")
            return
        
        # Procesar datos básicos (inventario ganadero)
        records_published = 0
        for _, row in cap400a_1.iterrows():
            try:
                # Crear mensaje con los campos relevantes
                message = {
                    'ANIO': int(row['ANIO']) if 'ANIO' in row and pd.notna(row['ANIO']) else 2021,
                    'CCDD': str(row['CCDD']) if 'CCDD' in row else '',
                    'CCPP': str(row['CCPP']) if 'CCPP' in row else '',
                    'CCDI': str(row['CCDI']) if 'CCDI' in row else '',
                    'CONGLOMERADO': str(row['CONGLOMERADO']) if 'CONGLOMERADO' in row else '',
                    'NSELUA': str(row['NSELUA']) if 'NSELUA' in row else '',
                    'UA': str(row['UA']) if 'UA' in row else '',
                    'CODIGO': str(row['CODIGO']) if 'CODIGO' in row else '',
                    'TIPO_ANIMAL': str(row[tipo_animal_col]) if tipo_animal_col in row and pd.notna(row[tipo_animal_col]) else '',
                    'CANTIDAD_ANIMALES': int(row[cantidad_col]) if cantidad_col in row and pd.notna(row[cantidad_col]) else 0,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Publicar mensaje
                publish_message(producer, KAFKA_TOPIC_PECUARIA, message)
                records_published += 1
                
                # Mostrar progreso cada 1000 registros
                if records_published % 1000 == 0:
                    logger.info(f"Progreso: {records_published} registros publicados")
                
            except Exception as e:
                logger.error(f"Error al publicar mensaje: {e}")
        
        logger.info(f"Se publicaron {records_published} registros pecuarios en Kafka (tema: {KAFKA_TOPIC_PECUARIA})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos del capítulo 400: {e}")
        raise

def process_cap700_cap800_data(producer):
    """Procesa datos de los capítulos 700 y 800 (Servicios agrarios)"""
    logger.info("Procesando datos de servicios agrarios (cap. 700 y 800)...")
    
    # Cargar archivos relacionados
    try:
        # Buscar archivos por patrón
        file_700 = find_file_by_pattern("Cap700")
        file_800 = find_file_by_pattern("Cap800")
        
        if not file_700 and not file_800:
            logger.error("No se encontraron archivos de servicios agrarios (cap. 700 o 800)")
            return
        
        # Procesar datos de capacitación
        if file_700:
            cap700 = pd.read_csv(file_700, low_memory=False)
            logger.info(f"Archivo cargado - {os.path.basename(file_700)}: {len(cap700)} registros")
            
            # Mostrar las columnas disponibles
            print("Columnas en Cap700:", cap700.columns.tolist())
            
            # Identificar columna de capacitación
            capacitacion_col = next((col for col in cap700.columns if 'P701' in col), None)
            
            if not capacitacion_col:
                logger.warning("No se encontró columna de capacitación en Cap700")
            
            records_published = 0
            for _, row in cap700.iterrows():
                try:
                    # Crear mensaje con los campos relevantes
                    message = {
                        'ANIO': int(row['ANIO']) if 'ANIO' in row and pd.notna(row['ANIO']) else 2021,
                        'CCDD': str(row['CCDD']) if 'CCDD' in row else '',
                        'CCPP': str(row['CCPP']) if 'CCPP' in row else '',
                        'CCDI': str(row['CCDI']) if 'CCDI' in row else '',
                        'CONGLOMERADO': str(row['CONGLOMERADO']) if 'CONGLOMERADO' in row else '',
                        'NSELUA': str(row['NSELUA']) if 'NSELUA' in row else '',
                        'UA': str(row['UA']) if 'UA' in row else '',
                        'CODIGO': str(row['CODIGO']) if 'CODIGO' in row else '',
                        'RECIBE_CAPACITACION': bool(row[capacitacion_col]) if capacitacion_col in row and pd.notna(row[capacitacion_col]) else False,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Publicar mensaje
                    publish_message(producer, KAFKA_TOPIC_SERVICIOS, message)
                    records_published += 1
                    
                    # Mostrar progreso cada 1000 registros
                    if records_published % 1000 == 0:
                        logger.info(f"Progreso: {records_published} registros publicados")
                    
                except Exception as e:
                    logger.error(f"Error al publicar mensaje: {e}")
            
            logger.info(f"Se publicaron {records_published} registros de servicios en Kafka (tema: {KAFKA_TOPIC_SERVICIOS})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos de servicios agrarios: {e}")
        raise

def process_cap500_data(producer):
    """Procesa datos del capítulo 500 (Riego)"""
    logger.info("Procesando datos del capítulo 500 (Riego)...")
    
    # Cargar archivos relacionados
    try:
        # Buscar archivo por patrón
        file_500ab = find_file_by_pattern("Cap500ab")
        
        if not file_500ab:
            logger.error("No se encontró el archivo de riego (cap. 500)")
            return
            
        cap500ab = pd.read_csv(file_500ab, low_memory=False)
        
        logger.info(f"Archivo cargado - {os.path.basename(file_500ab)}: {len(cap500ab)} registros")
        
        # Mostrar las columnas disponibles
        print("Columnas en Cap500ab:", cap500ab.columns.tolist())
        
        # Identificar columnas relevantes
        tipo_riego_col = next((col for col in cap500ab.columns if 'TIPO' in col), None)
        superficie_col = next((col for col in cap500ab.columns if 'SUP' in col), None)
        
        if not tipo_riego_col or not superficie_col:
            logger.warning("No se encontraron columnas de tipo de riego o superficie")
        
        # Procesar datos de riego
        records_published = 0
        for _, row in cap500ab.iterrows():
            try:
                # Crear mensaje con los campos relevantes
                message = {
                    'ANIO': int(row['ANIO']) if 'ANIO' in row and pd.notna(row['ANIO']) else 2021,
                    'CCDD': str(row['CCDD']) if 'CCDD' in row else '',
                    'CCPP': str(row['CCPP']) if 'CCPP' in row else '',
                    'CCDI': str(row['CCDI']) if 'CCDI' in row else '',
                    'CONGLOMERADO': str(row['CONGLOMERADO']) if 'CONGLOMERADO' in row else '',
                    'NSELUA': str(row['NSELUA']) if 'NSELUA' in row else '',
                    'UA': str(row['UA']) if 'UA' in row else '',
                    'CODIGO': str(row['CODIGO']) if 'CODIGO' in row else '',
                    'TIPO_RIEGO': str(row[tipo_riego_col]) if tipo_riego_col in row and pd.notna(row[tipo_riego_col]) else '',
                    'SUPERFICIE_RIEGO': float(row[superficie_col]) if superficie_col in row and pd.notna(row[superficie_col]) else 0.0,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Publicar mensaje
                publish_message(producer, KAFKA_TOPIC_RIEGO, message)
                records_published += 1
                
                # Mostrar progreso cada 1000 registros
                if records_published % 1000 == 0:
                    logger.info(f"Progreso: {records_published} registros publicados")
                
            except Exception as e:
                logger.error(f"Error al publicar mensaje: {e}")
        
        logger.info(f"Se publicaron {records_published} registros de riego en Kafka (tema: {KAFKA_TOPIC_RIEGO})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos de riego: {e}")
        raise

def main():
    """Función principal del procesador de datos"""
    logger.info("Iniciando procesamiento de datos de la ENA 2021")
    
    # Esperar a que los servicios estén disponibles
    logger.info("Esperando a que los servicios estén disponibles...")
    time.sleep(30)
    
    try:
        # 1. Verificar archivos disponibles
        csv_files = list_csv_files()
        if not csv_files:
            logger.error("No se encontraron archivos CSV en el directorio de datos")
            return
        
        # 2. Cargar todas las dimensiones
        load_all_dimensions()
        
        # 3. Crear productor de Kafka
        producer = create_producer()
        
        # 4. Procesar y publicar datos en Kafka por capítulos
        process_cap200_data(producer)
        process_cap400_data(producer)
        process_cap700_cap800_data(producer)
        process_cap500_data(producer)
        
        # 5. Cerrar productor
        producer.close()
        
        logger.info("Procesamiento de datos completado exitosamente")
        
    except Exception as e:
        logger.error(f"Error en el procesamiento principal: {e}")
        raise


if __name__ == "__main__":
    main()