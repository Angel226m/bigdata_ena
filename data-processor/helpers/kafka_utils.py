# Utilidades para Kafka 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilidades para interactuar con Apache Kafka
"""

import os
import json
import logging
from kafka import KafkaProducer, KafkaConsumer

# Configurar logging
logger = logging.getLogger('kafka_utils')

# Constantes
 
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')


def create_producer():
    """Crea y devuelve un productor de Kafka"""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        logger.info(f"Productor Kafka creado (bootstrap_servers: {KAFKA_BOOTSTRAP_SERVERS})")
        return producer
    except Exception as e:
        logger.error(f"Error al crear productor Kafka: {e}")
        raise


def create_consumer(topic, group_id):
    """Crea y devuelve un consumidor de Kafka"""
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id=group_id,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        logger.info(f"Consumidor Kafka creado (bootstrap_servers: {KAFKA_BOOTSTRAP_SERVERS}, topic: {topic})")
        return consumer
    except Exception as e:
        logger.error(f"Error al crear consumidor Kafka: {e}")
        raise


def publish_message(producer, topic, message):
    """Publica un mensaje en un tema de Kafka"""
    try:
        future = producer.send(topic, message)
        producer.flush()
        record_metadata = future.get(timeout=10)
        logger.debug(f"Mensaje publicado en tema={record_metadata.topic}, partición={record_metadata.partition}, offset={record_metadata.offset}")
        return record_metadata
    except Exception as e:
        logger.error(f"Error al publicar mensaje en Kafka (tema {topic}): {e}")
        raise