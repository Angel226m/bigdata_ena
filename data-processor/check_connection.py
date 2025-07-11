#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para verificar la conexión a Kafka y PostgreSQL
"""

import os
import sys
import time
import logging
import socket
import psycopg2
from kafka import KafkaProducer, KafkaConsumer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('connection_checker')

def check_host(host, port):
    """Verifica si un host está disponible en el puerto especificado"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except socket.error as e:
        logger.error(f"Error al verificar {host}:{port} - {e}")
        return False

def check_kafka():
    """Verifica la conexión a Kafka"""
    kafka_host = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092').split(':')[0]
    kafka_port = int(os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092').split(':')[1])
    
    logger.info(f"Verificando conexión a Kafka en {kafka_host}:{kafka_port}...")
    
    if check_host(kafka_host, kafka_port):
        logger.info("✅ Kafka está disponible en el puerto especificado")
    else:
        logger.error("❌ No se puede conectar a Kafka")
        return False
    
    try:
        # Intentar crear un productor
        producer = KafkaProducer(
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092'),
            api_version=(0, 10, 1)
        )
        logger.info("✅ Productor Kafka creado correctamente")
        producer.close()
        
        # Intentar crear un consumidor
        consumer = KafkaConsumer(
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092'),
            api_version=(0, 10, 1),
            group_id="connection_test",
            auto_offset_reset='earliest'
        )
        logger.info("✅ Consumidor Kafka creado correctamente")
        consumer.close()
        
        return True
    except Exception as e:
        logger.error(f"❌ Error al conectar a Kafka: {e}")
        return False

def check_postgres():
    """Verifica la conexión a PostgreSQL"""
    postgres_host = os.environ.get('POSTGRES_HOST', 'postgres')
    postgres_port = 5432
    
    logger.info(f"Verificando conexión a PostgreSQL en {postgres_host}:{postgres_port}...")
    
    if check_host(postgres_host, postgres_port):
        logger.info("✅ PostgreSQL está disponible en el puerto especificado")
    else:
        logger.error("❌ No se puede conectar a PostgreSQL")
        return False
    
    try:
        # Intentar conectar a PostgreSQL
        conn = psycopg2.connect(
            host=postgres_host,
            database=os.environ.get('POSTGRES_DB', 'ena_database'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', 'postgres')
        )
        logger.info("✅ Conexión a PostgreSQL establecida correctamente")
        
        # Verificar si las tablas ya están creadas
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'dim_ubicacion'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            logger.info("✅ Las tablas ya están creadas en PostgreSQL")
        else:
            logger.warning("⚠️ Las tablas aún no están creadas en PostgreSQL")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"❌ Error al conectar a PostgreSQL: {e}")
        return False

def check_data_files():
    """Verifica si los archivos CSV existen en el directorio de datos"""
    data_dir = '/data'
    required_files = [
        "Cap100_1 ENA 2021.csv",
        "Cap200a ENA 2021.csv",
        "Cap400a_1 ENA 2021.csv"
    ]
    
    logger.info("Verificando archivos CSV en el directorio de datos...")
    
    missing_files = []
    for file in required_files:
        file_path = os.path.join(data_dir, file)
        if not os.path.exists(file_path):
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"❌ Faltan {len(missing_files)} archivos requeridos:")
        for file in missing_files:
            logger.error(f"   - {file}")
        return False
    else:
        logger.info("✅ Todos los archivos requeridos están presentes")
        return True

def main():
    """Función principal"""
    logger.info("Iniciando verificación de conexiones...")
    
    # Esperar a que los servicios estén disponibles
    max_retries = 5
    retry_interval = 5  # segundos
    
    for i in range(max_retries):
        logger.info(f"Intento {i+1}/{max_retries} de conexión...")
        
        kafka_ok = check_kafka()
        postgres_ok = check_postgres()
        files_ok = check_data_files()
        
        if kafka_ok and postgres_ok and files_ok:
            logger.info("✅ Todas las verificaciones pasaron correctamente")
            return 0
        
        if i < max_retries - 1:
            logger.info(f"Esperando {retry_interval} segundos antes de reintentar...")
            time.sleep(retry_interval)
    
    logger.error("❌ No se pudieron establecer todas las conexiones después de varios intentos")
    return 1

if __name__ == "__main__":
    sys.exit(main())