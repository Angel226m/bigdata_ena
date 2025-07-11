# Script principal de procesamiento 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script principal para procesamiento de datos de la ENA 2021
Este script coordina todo el procesamiento de datos:
1. Carga los archivos CSV
2. Procesa y carga tablas dimensionales
3. Publica datos en Kafka
4. Procesa y carga tablas de hechos
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
from load_dimensions import load_all_dimensions

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/ena_processing.log')
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
        cap200a = pd.read_csv(os.path.join(DATA_DIR, "Cap200a ENA 2021.csv"), low_memory=False)
        cap200c = pd.read_csv(os.path.join(DATA_DIR, "Cap200c ENA 2021.csv"), low_memory=False)
        cap200d = pd.read_csv(os.path.join(DATA_DIR, "Cap200d ENA 2021.csv"), low_memory=False)
        cap200e = pd.read_csv(os.path.join(DATA_DIR, "Cap200e ENA 2021.csv"), low_memory=False)
        
        logger.info(f"Archivos cargados - Cap200a: {len(cap200a)} registros, Cap200c: {len(cap200c)} registros")
        
        # Procesar datos básicos
        base_agricola = cap200a.merge(
            cap200c, 
            on=['ANIO', 'CCDD', 'CCPP', 'CCDI', 'CONGLOMERADO', 'NSELUA', 'UA', 'CODIGO', 'P204_COD'],
            how='inner'
        )
        
        # Agregar datos de costos
        base_agricola = base_agricola.merge(
            cap200e,
            on=['ANIO', 'CCDD', 'CCPP', 'CCDI', 'CONGLOMERADO', 'NSELUA', 'UA', 'CODIGO', 'P204_COD'],
            how='left'
        )
        
        # Agregar datos de destino de producción
        base_agricola = base_agricola.merge(
            cap200d,
            on=['ANIO', 'CCDD', 'CCPP', 'CCDI', 'CONGLOMERADO', 'NSELUA', 'UA', 'CODIGO', 'P204_COD'],
            how='left'
        )
        
        # Calcular producción total combinando parte entera y decimal
        base_agricola['PRODUCCION_TOTAL'] = base_agricola['P218C_PROD_CORTE_ENT'].fillna(0) + \
                                           base_agricola['P218C_PROD_CORTE_DEC'].fillna(0)
        
        # Calcular rendimiento (producción / superficie cosechada)
        base_agricola['RENDIMIENTO'] = base_agricola.apply(
            lambda x: x['PRODUCCION_TOTAL'] / x['P218B'] if x['P218B'] > 0 else 0, 
            axis=1
        )
        
        # Publicar datos en Kafka
        for _, row in base_agricola.iterrows():
            # Crear mensaje con los campos relevantes
            message = {
                'ANIO': int(row['ANIO']),
                'CCDD': str(row['CCDD']),
                'CCPP': str(row['CCPP']),
                'CCDI': str(row['CCDI']),
                'CONGLOMERADO': str(row['CONGLOMERADO']),
                'NSELUA': str(row['NSELUA']),
                'UA': str(row['UA']),
                'CODIGO': str(row['CODIGO']),
                'P204_COD': str(row['P204_COD']),
                'P204_NOM': str(row['P204_NOM']) if 'P204_NOM' in row else '',
                'P204_TIPO': str(row['P204_TIPO']) if 'P204_TIPO' in row else '',
                'SUPERFICIE_SEMBRADA': float(row['P218A']) if pd.notna(row['P218A']) else 0.0,
                'SUPERFICIE_COSECHADA': float(row['P218B']) if pd.notna(row['P218B']) else 0.0,
                'PRODUCCION_TOTAL': float(row['PRODUCCION_TOTAL']),
                'RENDIMIENTO': float(row['RENDIMIENTO']),
                'timestamp': datetime.now().isoformat()
            }
            
            # Agregar campos de costos si están disponibles
            if 'P235_COSTO_SEMILLA' in row:
                message['COSTO_SEMILLA'] = float(row['P235_COSTO_SEMILLA']) if pd.notna(row['P235_COSTO_SEMILLA']) else 0.0
            
            # Agregar campos de destino si están disponibles
            if 'P232A_VENTA' in row:
                message['DESTINO_VENTA'] = float(row['P232A_VENTA']) if pd.notna(row['P232A_VENTA']) else 0.0
            
            # Publicar mensaje
            publish_message(producer, KAFKA_TOPIC_AGRICOLA, message)
        
        logger.info(f"Se publicaron {len(base_agricola)} registros en Kafka (tema: {KAFKA_TOPIC_AGRICOLA})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos del capítulo 200: {e}")
        raise


def process_cap400_data(producer):
    """Procesa datos del capítulo 400 (Producción Pecuaria)"""
    logger.info("Procesando datos del capítulo 400 (Producción Pecuaria)...")
    
    # Cargar archivos relacionados
    try:
        cap400a_1 = pd.read_csv(os.path.join(DATA_DIR, "Cap400a_1 ENA 2021.csv"), low_memory=False)
        cap400a_2 = pd.read_csv(os.path.join(DATA_DIR, "Cap400a_2 ENA 2021.csv"), low_memory=False)
        cap400c = pd.read_csv(os.path.join(DATA_DIR, "Cap400c ENA 2021.csv"), low_memory=False)
        
        logger.info(f"Archivos cargados - Cap400a_1: {len(cap400a_1)} registros, Cap400a_2: {len(cap400a_2)} registros")
        
        # Procesar datos básicos (inventario ganadero)
        for _, row in cap400a_1.iterrows():
            # Crear mensaje con los campos relevantes
            message = {
                'ANIO': int(row['ANIO']) if 'ANIO' in row else 2021,
                'CCDD': str(row['CCDD']),
                'CCPP': str(row['CCPP']),
                'CCDI': str(row['CCDI']),
                'CONGLOMERADO': str(row['CONGLOMERADO']),
                'NSELUA': str(row['NSELUA']),
                'UA': str(row['UA']),
                'CODIGO': str(row['CODIGO']),
                'TIPO_ANIMAL': str(row['P402_ESPECIE']) if 'P402_ESPECIE' in row else '',
                'CANTIDAD_ANIMALES': int(row['P402_NRO']) if 'P402_NRO' in row and pd.notna(row['P402_NRO']) else 0,
                'timestamp': datetime.now().isoformat()
            }
            
            # Publicar mensaje
            publish_message(producer, KAFKA_TOPIC_PECUARIA, message)
        
        logger.info(f"Se publicaron {len(cap400a_1)} registros pecuarios en Kafka (tema: {KAFKA_TOPIC_PECUARIA})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos del capítulo 400: {e}")
        raise


def process_cap700_cap800_data(producer):
    """Procesa datos de los capítulos 700 y 800 (Servicios agrarios)"""
    logger.info("Procesando datos de servicios agrarios (cap. 700 y 800)...")
    
    # Cargar archivos relacionados
    try:
        cap700 = pd.read_csv(os.path.join(DATA_DIR, "Cap700 ENA 2021.csv"), low_memory=False)
        cap800 = pd.read_csv(os.path.join(DATA_DIR, "Cap800 ENA 2021.csv"), low_memory=False)
        
        logger.info(f"Archivos cargados - Cap700: {len(cap700)} registros, Cap800: {len(cap800)} registros")
        
        # Procesar datos de capacitación
        for _, row in cap700.iterrows():
            # Crear mensaje con los campos relevantes
            message = {
                'ANIO': int(row['ANIO']) if 'ANIO' in row else 2021,
                'CCDD': str(row['CCDD']),
                'CCPP': str(row['CCPP']),
                'CCDI': str(row['CCDI']),
                'CONGLOMERADO': str(row['CONGLOMERADO']),
                'NSELUA': str(row['NSELUA']),
                'UA': str(row['UA']),
                'CODIGO': str(row['CODIGO']),
                'RECIBE_CAPACITACION': bool(row['P701']) if 'P701' in row and pd.notna(row['P701']) else False,
                'timestamp': datetime.now().isoformat()
            }
            
            # Publicar mensaje
            publish_message(producer, KAFKA_TOPIC_SERVICIOS, message)
        
        logger.info(f"Se publicaron {len(cap700)} registros de servicios en Kafka (tema: {KAFKA_TOPIC_SERVICIOS})")
    
    except Exception as e:
        logger.error(f"Error al procesar datos de servicios agrarios: {e}")
        raise


def process_cap500_data(producer):
    """Procesa datos del capítulo 500 (Riego)"""
    logger.info("Procesando datos del capítulo 500 (Riego)...")
    
    # Cargar archivos relacionados
    try:
        cap500ab = pd.read_csv(os.path.join(DATA_DIR, "Cap500ab ENA 2021.csv"), low_memory=False)
        
        logger.info(f"Archivos cargados - Cap500ab: {len(cap500ab)} registros")
        
        # Procesar datos de riego
        for _, row in cap500ab.iterrows():
            # Crear mensaje con los campos relevantes
            message = {
                'ANIO': int(row['ANIO']) if 'ANIO' in row else 2021,
                'CCDD': str(row['CCDD']),
                'CCPP': str(row['CCPP']),
                'CCDI': str(row['CCDI']),
                'CONGLOMERADO': str(row['CONGLOMERADO']),
                'NSELUA': str(row['NSELUA']),
                'UA': str(row['UA']),
                'CODIGO': str(row['CODIGO']),
                'TIPO_RIEGO': str(row['P509_TIPO']) if 'P509_TIPO' in row else '',
                'SUPERFICIE_RIEGO': float(row['P509_SUP']) if 'P509_SUP' in row and pd.notna(row['P509_SUP']) else 0.0,
                'timestamp': datetime.now().isoformat()
            }
            
            # Publicar mensaje
            publish_message(producer, KAFKA_TOPIC_RIEGO, message)
        
        logger.info(f"Se publicaron {len(cap500ab)} registros de riego en Kafka (tema: {KAFKA_TOPIC_RIEGO})")
    
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