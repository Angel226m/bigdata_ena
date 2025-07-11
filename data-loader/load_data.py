#!/usr/bin/env python3
"""
Script para carga directa de datos de la ENA 2021 en PostgreSQL.
No usa Kafka, carga los datos directamente desde CSV a PostgreSQL.
"""

import os
import pandas as pd
import psycopg2
import logging
import time
from sqlalchemy import create_engine
import sys
import glob
import chardet

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración desde variables de entorno o valores por defecto
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'ena_database')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'postgres')
DATA_DIR = os.environ.get('DATA_DIR', '/data')

def detect_encoding(file_path):
    """Detecta la codificación de un archivo"""
    try:
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read(10000))
        logger.info(f"Codificación detectada para {file_path}: {result['encoding']} (confianza: {result['confidence']})")
        return result['encoding']
    except Exception as e:
        logger.warning(f"Error al detectar codificación: {e}, usando 'latin1'")
        return 'latin1'

def read_csv_with_encoding(file_path):
    """Lee un archivo CSV probando diferentes codificaciones"""
    encodings = ['utf-8', 'latin1', 'ISO-8859-1', 'cp1252']
    
    # Primero, intentar detectar automáticamente
    detected_encoding = detect_encoding(file_path)
    if detected_encoding:
        encodings.insert(0, detected_encoding)
    
    for encoding in encodings:
        try:
            logger.info(f"Intentando leer {file_path} con codificación {encoding}")
            return pd.read_csv(file_path, encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            logger.warning(f"Error de codificación con {encoding}")
            continue
        except Exception as e:
            logger.warning(f"Error al leer {file_path} con {encoding}: {e}")
            continue
    
    # Si llegamos aquí, intentamos una última opción con manejo de errores
    try:
        logger.info(f"Intentando leer {file_path} con manejo de errores")
        return pd.read_csv(file_path, encoding='latin1', errors='replace', low_memory=False)
    except Exception as e:
        logger.error(f"No se pudo leer {file_path} con ninguna codificación: {e}")
        raise

def get_db_connection():
    """Establece y retorna una conexión a PostgreSQL"""
    retry_count = 0
    max_retries = 10  # Aumentado a 10 intentos
    
    while retry_count < max_retries:
        try:
            # Intentar imprimir la resolución del host para diagnóstico
            try:
                import socket
                logger.info(f"Intentando resolver host 'postgres': {socket.gethostbyname('postgres')}")
            except Exception as e:
                logger.warning(f"No se pudo resolver el host 'postgres': {e}")
            
            conn = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
            logger.info("Conexión a PostgreSQL exitosa")
            return conn
        except Exception as e:
            retry_count += 1
            logger.warning(f"Intento {retry_count}/{max_retries} de conexión a PostgreSQL falló: {e}")
            if retry_count >= max_retries:
                logger.error(f"Error al conectar a PostgreSQL después de {max_retries} intentos: {e}")
                raise
            time.sleep(10)  # Esperar 10 segundos antes de reintentar

def get_sqlalchemy_engine():
    """Establece y retorna un motor de SQLAlchemy"""
    try:
        return create_engine(f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}')
    except Exception as e:
        logger.error(f"Error al crear engine SQLAlchemy: {e}")
        raise

def find_file(pattern):
    """Busca un archivo que coincida con el patrón en el directorio de datos"""
    files = glob.glob(os.path.join(DATA_DIR, pattern))
    if files:
        return files[0]
    return None

def ensure_schema_exists():
    """Verifica que el esquema ena existe y lo crea si es necesario"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si el esquema ena existe
        cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'ena'")
        if not cursor.fetchone():
            logger.info("El esquema 'ena' no existe. Creándolo...")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS ena")
            conn.commit()
            logger.info("Esquema 'ena' creado exitosamente")
        else:
            logger.info("El esquema 'ena' ya existe")
            
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error al verificar/crear esquema: {e}")
        return False

def clear_existing_data():
    """Limpia datos existentes para evitar conflictos de unicidad"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Eliminar datos de las tablas de hechos primero (por restricciones de clave foránea)
        logger.info("Limpiando tablas de hechos...")
        cursor.execute("TRUNCATE ena.fact_produccion_agricola CASCADE")
        cursor.execute("TRUNCATE ena.fact_produccion_pecuaria CASCADE")
        cursor.execute("TRUNCATE ena.fact_servicios CASCADE")
        
        # Luego eliminar datos de las tablas dimensionales
        logger.info("Limpiando tablas dimensionales...")
        cursor.execute("TRUNCATE ena.dim_ubicacion CASCADE")
        cursor.execute("TRUNCATE ena.dim_productor CASCADE")
        cursor.execute("TRUNCATE ena.dim_cultivo CASCADE")
        cursor.execute("TRUNCATE ena.dim_animal CASCADE")
        cursor.execute("TRUNCATE ena.dim_tiempo CASCADE")
        cursor.execute("TRUNCATE ena.dim_tecnologia CASCADE")
        
        conn.commit()
        logger.info("Tablas limpiadas exitosamente")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error al limpiar datos existentes: {e}")
        return False

def ensure_tables_exist():
    """Verifica que las tablas necesarias existen y las crea si es necesario"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar si la tabla dim_ubicacion existe
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'ena' AND table_name = 'dim_ubicacion'
        """)
        
        if not cursor.fetchone():
            logger.info("Las tablas no existen. Creando esquema...")
            
            # Crear tablas dimensionales
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.dim_ubicacion (
                id_ubicacion SERIAL PRIMARY KEY,
                ccdd VARCHAR(2),
                nombredd VARCHAR(100),
                ccpp VARCHAR(2),
                nombrepv VARCHAR(100),
                ccdi VARCHAR(2),
                nombredi VARCHAR(100),
                region VARCHAR(50),
                dominio VARCHAR(50),
                UNIQUE(ccdd, ccpp, ccdi)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.dim_productor (
                id_productor SERIAL PRIMARY KEY,
                codigo VARCHAR(20),
                p102_1 VARCHAR(200),
                p102_2 VARCHAR(200),
                p105_n VARCHAR(200),
                sexo VARCHAR(20),
                edad INTEGER,
                experiencia INTEGER
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.dim_cultivo (
                id_cultivo SERIAL PRIMARY KEY,
                p204_cod VARCHAR(10),
                p204_nom VARCHAR(200),
                p204_tipo VARCHAR(100)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.dim_animal (
                id_animal SERIAL PRIMARY KEY,
                codigo VARCHAR(10),
                nombre VARCHAR(100),
                tipo VARCHAR(50)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.dim_tiempo (
                id_tiempo SERIAL PRIMARY KEY,
                anio INTEGER,
                trimestre INTEGER,
                mes INTEGER
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.dim_tecnologia (
                id_tecnologia SERIAL PRIMARY KEY,
                usa_fertilizantes BOOLEAN,
                tipo_fertilizante VARCHAR(100),
                tiene_analisis_suelo BOOLEAN,
                practica_conservacion BOOLEAN,
                tipo_riego VARCHAR(50),
                fuente_agua VARCHAR(50)
            )""")
            
            # Crear tablas de hechos
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.fact_produccion_agricola (
                id_produccion SERIAL PRIMARY KEY,
                id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
                id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
                id_cultivo INTEGER REFERENCES ena.dim_cultivo(id_cultivo),
                id_tiempo INTEGER REFERENCES ena.dim_tiempo(id_tiempo),
                id_tecnologia INTEGER REFERENCES ena.dim_tecnologia(id_tecnologia),
                conglomerado VARCHAR(20),
                nselua VARCHAR(20),
                ua VARCHAR(20),
                factor DECIMAL(10,4),
                superficie_sembrada DECIMAL(12,2),
                superficie_cosechada DECIMAL(12,2),
                produccion_total DECIMAL(12,2),
                rendimiento DECIMAL(12,2),
                costo_semillas DECIMAL(12,2),
                costo_fertilizantes DECIMAL(12,2),
                costo_plaguicidas DECIMAL(12,2),
                costo_total DECIMAL(12,2),
                destino_venta DECIMAL(12,2),
                destino_autoconsumo DECIMAL(12,2)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.fact_produccion_pecuaria (
                id_produccion SERIAL PRIMARY KEY,
                id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
                id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
                id_animal INTEGER REFERENCES ena.dim_animal(id_animal),
                id_tiempo INTEGER REFERENCES ena.dim_tiempo(id_tiempo),
                conglomerado VARCHAR(20),
                nselua VARCHAR(20),
                ua VARCHAR(20),
                factor DECIMAL(10,4),
                numero_animales INTEGER,
                produccion_leche DECIMAL(12,2),
                produccion_huevos DECIMAL(12,2),
                produccion_carne DECIMAL(12,2),
                costo_alimentacion DECIMAL(12,2),
                costo_sanitario DECIMAL(12,2),
                costo_total DECIMAL(12,2)
            )""")
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ena.fact_servicios (
                id_servicio SERIAL PRIMARY KEY,
                id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
                id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
                recibe_capacitacion BOOLEAN,
                institucion_capacitadora VARCHAR(100),
                tipo_asistencia VARCHAR(100),
                frecuencia_asistencia VARCHAR(50),
                es_organizado BOOLEAN,
                tipo_organizacion VARCHAR(100),
                beneficios_organizacion VARCHAR(200)
            )""")
            
            # Crear índices para optimizar consultas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_agricola_ubicacion ON ena.fact_produccion_agricola(id_ubicacion)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_agricola_productor ON ena.fact_produccion_agricola(id_productor)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_agricola_cultivo ON ena.fact_produccion_agricola(id_cultivo)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_ubicacion ON ena.fact_produccion_pecuaria(id_ubicacion)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_productor ON ena.fact_produccion_pecuaria(id_productor)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_servicios_productor ON ena.fact_servicios(id_productor)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_servicios_ubicacion ON ena.fact_servicios(id_ubicacion)")
            
            conn.commit()
            logger.info("Tablas creadas exitosamente")
        else:
            logger.info("Las tablas ya existen")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error al verificar/crear tablas: {e}")
        return False

def load_dimension_data():
    """Carga datos dimensionales desde archivos CSV a PostgreSQL"""
    try:
        logger.info("Iniciando carga de dimensiones")
        
        # Buscar los archivos necesarios
        file_cap100_1 = find_file("*Cap100_1*.csv")
        file_cap200a = find_file("*Cap200a*.csv") or find_file("*Cap200ab*.csv")
        
        if not file_cap100_1 or not file_cap200a:
            logger.error(f"Archivos críticos no encontrados: Cap100_1.csv o Cap200a.csv")
            logger.error(f"Archivos encontrados en {DATA_DIR}: {os.listdir(DATA_DIR)}")
            return False
            
        logger.info(f"Archivo Cap100_1 encontrado: {file_cap100_1}")
        logger.info(f"Archivo Cap200a encontrado: {file_cap200a}")
        
        # Cargar dimensión ubicación (Cap100_1)
        logger.info(f"Procesando archivo: {file_cap100_1}")
        df_ubicacion_raw = read_csv_with_encoding(file_cap100_1)
        
        # Verificar columnas de ubicación
        if 'CCDD' in df_ubicacion_raw.columns and 'NOMBREDD' in df_ubicacion_raw.columns:
            cols_to_keep = [col for col in ['CCDD', 'NOMBREDD', 'CCPP', 'NOMBREPV', 'CCDI', 'NOMBREDI', 'REGION', 'DOMINIO'] 
                            if col in df_ubicacion_raw.columns]
            df_ubicacion = df_ubicacion_raw[cols_to_keep].copy()
            
            # Asegurar que valores no son nulos
            for col in ['CCDD', 'CCPP', 'CCDI']:
                if col in df_ubicacion.columns:
                    df_ubicacion[col] = df_ubicacion[col].fillna('00')
                else:
                    df_ubicacion[col] = '00'
            
            # Aplicar lowercase a nombres de columnas
            new_cols = {col: col.lower() for col in df_ubicacion.columns}
            df_ubicacion = df_ubicacion.rename(columns=new_cols)
            
            # Filtrar duplicados por ccdd, ccpp, ccdi
            df_ubicacion = df_ubicacion.drop_duplicates(subset=['ccdd', 'ccpp', 'ccdi'])
        else:
            logger.warning("Columnas necesarias no encontradas en Cap100_1.csv. Usando estructura genérica.")
            df_ubicacion = pd.DataFrame({
                'ccdd': ['01', '02', '03'],
                'nombredd': ['LIMA', 'AREQUIPA', 'CUSCO'],
                'ccpp': ['01', '01', '01'],
                'nombrepv': ['LIMA', 'AREQUIPA', 'CUSCO'],
                'ccdi': ['01', '01', '01'],
                'nombredi': ['LIMA', 'AREQUIPA', 'CUSCO'],
                'region': ['Costa', 'Sierra', 'Sierra'],
                'dominio': ['Urbano', 'Urbano', 'Rural']
            })
        
        # Cargar dimensión productor (Cap100_1)
        df_productor_raw = read_csv_with_encoding(file_cap100_1)
        
        # Verificar si existe la columna CODIGO
        if 'CODIGO' in df_productor_raw.columns:
            # Crear una columna código string única para cada fila
            # Esto evita conflictos cuando hay múltiples filas con mismo CODIGO
            df_productor_raw['CODIGO_UNICO'] = df_productor_raw['CODIGO'].astype(str)
            
            # Preparar dataframe para productor
            cols_to_keep = ['CODIGO_UNICO']
            for col in ['P102_1', 'P102_2', 'P105_N']:
                if col in df_productor_raw.columns:
                    cols_to_keep.append(col)
            
            # Seleccionar columnas relevantes
            df_productor = df_productor_raw[cols_to_keep].copy()
            
            # Renombrar columnas
            new_cols = {'CODIGO_UNICO': 'codigo'}
            for col in cols_to_keep[1:]:
                new_cols[col] = col.lower()
            
            df_productor = df_productor.rename(columns=new_cols)
            
            # Agregar columnas faltantes
            if 'p102_1' not in df_productor.columns:
                df_productor['p102_1'] = None
            if 'p102_2' not in df_productor.columns:
                df_productor['p102_2'] = None
            if 'p105_n' not in df_productor.columns:
                df_productor['p105_n'] = None
                
            # Agregar columnas adicionales
            df_productor['sexo'] = None
            df_productor['edad'] = None
            df_productor['experiencia'] = None
            
            # Eliminar duplicados de código
            df_productor = df_productor.drop_duplicates(subset=['codigo'])
        else:
            logger.warning("No se encontró la columna CODIGO en Cap100_1.csv. Usando datos genéricos.")
            df_productor = pd.DataFrame({
                'codigo': ['P001', 'P002', 'P003'],
                'p102_1': ['Pequeño', 'Mediano', 'Grande'],
                'p102_2': ['Natural', 'Jurídica', 'Natural'],
                'p105_n': ['Primaria', 'Secundaria', 'Superior'],
                'sexo': [None, None, None],
                'edad': [None, None, None],
                'experiencia': [None, None, None]
            })
        
        # Cargar dimensión cultivo (Cap200a)
        df_cultivo_raw = read_csv_with_encoding(file_cap200a)
        
        # Buscar columnas que puedan contener información de cultivos
        cultivo_cols = [col for col in df_cultivo_raw.columns if 'P204_COD' in col or 'COD' in col]
        if cultivo_cols:
            cultivo_cod_col = cultivo_cols[0]
            cultivo_nom_col = next((col for col in df_cultivo_raw.columns if 'P204_NOM' in col or 'NOM' in col), None)
            cultivo_tipo_col = next((col for col in df_cultivo_raw.columns if 'P204_TIPO' in col or 'TIPO' in col), None)
            
            cols_to_use = [cultivo_cod_col]
            if cultivo_nom_col:
                cols_to_use.append(cultivo_nom_col)
            if cultivo_tipo_col:
                cols_to_use.append(cultivo_tipo_col)
                
            df_cultivo = df_cultivo_raw[cols_to_use].copy()
            
            # Renombrar columnas
            df_cultivo.columns = ['p204_cod'] + (['p204_nom'] if cultivo_nom_col else []) + (['p204_tipo'] if cultivo_tipo_col else [])
            
            # Agregar columnas faltantes con valores predeterminados
            if 'p204_nom' not in df_cultivo.columns:
                df_cultivo['p204_nom'] = 'No especificado'
            if 'p204_tipo' not in df_cultivo.columns:
                df_cultivo['p204_tipo'] = 'No especificado'
            
            # Eliminar duplicados y nulos
            df_cultivo = df_cultivo.dropna(subset=['p204_cod']).drop_duplicates(subset=['p204_cod'])
        else:
            logger.warning("No se encontraron columnas necesarias para cultivos. Usando datos genéricos.")
            df_cultivo = pd.DataFrame({
                'p204_cod': ['C001', 'C002', 'C003'],
                'p204_nom': ['PAPA', 'MAIZ', 'ARROZ'],
                'p204_tipo': ['Tuberculo', 'Cereal', 'Cereal']
            })
        
        # Cargar dimensión animal (genérica)
        df_animal = pd.DataFrame({
            'codigo': ['01', '02', '03', '04', '05', '07'],
            'nombre': ['VACUNO', 'OVINO', 'PORCINO', 'CAPRINO', 'ALPACA', 'AVES'],
            'tipo': ['Principal', 'Principal', 'Principal', 'Principal', 'Principal', 'Principal']
        })
        
        # Cargar dimensión tiempo (basado en el año de la encuesta)
        df_tiempo = pd.DataFrame([{'anio': 2021, 'trimestre': 0, 'mes': 0}])
        
        # Cargar dimensión tecnología (genérica)
        df_tecnologia = pd.DataFrame([
            {'usa_fertilizantes': True, 'tipo_fertilizante': 'Químico', 'tiene_analisis_suelo': True, 'practica_conservacion': True, 'tipo_riego': 'Aspersión', 'fuente_agua': 'Río'},
            {'usa_fertilizantes': True, 'tipo_fertilizante': 'Orgánico', 'tiene_analisis_suelo': False, 'practica_conservacion': True, 'tipo_riego': 'Goteo', 'fuente_agua': 'Pozo'},
            {'usa_fertilizantes': False, 'tipo_fertilizante': 'Ninguno', 'tiene_analisis_suelo': False, 'practica_conservacion': False, 'tipo_riego': 'Gravedad', 'fuente_agua': 'Laguna'},
            {'usa_fertilizantes': True, 'tipo_fertilizante': 'Foliar', 'tiene_analisis_suelo': True, 'practica_conservacion': False, 'tipo_riego': 'Sin riego', 'fuente_agua': 'Ninguna'}
        ])
        
        # Obtener conexión a la base de datos
        engine = get_sqlalchemy_engine()
        
        # Guardar dimensiones en PostgreSQL
        logger.info("Cargando dimensiones en PostgreSQL")
        
        # Usar modo 'replace' en lugar de 'append' para evitar conflictos de clave única
        df_ubicacion.to_sql('dim_ubicacion', engine, schema='ena', if_exists='append', index=False)
        logger.info(f"Dimensión ubicación: {len(df_ubicacion)} registros cargados")
        
        df_productor.to_sql('dim_productor', engine, schema='ena', if_exists='append', index=False)
        logger.info(f"Dimensión productor: {len(df_productor)} registros cargados")
        
        df_cultivo.to_sql('dim_cultivo', engine, schema='ena', if_exists='append', index=False)
        logger.info(f"Dimensión cultivo: {len(df_cultivo)} registros cargados")
        
        df_animal.to_sql('dim_animal', engine, schema='ena', if_exists='append', index=False)
        logger.info(f"Dimensión animal: {len(df_animal)} registros cargados")
        
        df_tiempo.to_sql('dim_tiempo', engine, schema='ena', if_exists='append', index=False)
        logger.info(f"Dimensión tiempo: {len(df_tiempo)} registros cargados")
        
        df_tecnologia.to_sql('dim_tecnologia', engine, schema='ena', if_exists='append', index=False)
        logger.info(f"Dimensión tecnología: {len(df_tecnologia)} registros cargados")
        
        logger.info("Carga de dimensiones completada exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"Error en la carga de dimensiones: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def load_agricultural_data():
    """Carga datos agrícolas directamente a PostgreSQL"""
    try:
        logger.info("Iniciando carga de datos agrícolas")
        
        # Buscar los archivos necesarios
        file_cap200a = find_file("*Cap200a*.csv") or find_file("*Cap200ab*.csv")
        if not file_cap200a:
            logger.error(f"Archivo Cap200a no encontrado")
            return False
            
        file_cap200c = find_file("*Cap200c*.csv")
        file_cap200d = find_file("*Cap200d*.csv") 
        file_cap200e = find_file("*Cap200e*.csv")
        
        logger.info(f"Archivos encontrados: {file_cap200a}, {file_cap200c}, {file_cap200d}, {file_cap200e}")
        
        # Leer datos agrícolas
        df_agricola = read_csv_with_encoding(file_cap200a)
        
        # Leer datos complementarios si existen
        if file_cap200c and os.path.exists(file_cap200c):
            df_cosecha = read_csv_with_encoding(file_cap200c)
        else:
            df_cosecha = pd.DataFrame()
            logger.warning("No se encontró el archivo Cap200c.csv")
        
        if file_cap200d and os.path.exists(file_cap200d):
            df_destino = read_csv_with_encoding(file_cap200d)
        else:
            df_destino = pd.DataFrame()
            logger.warning("No se encontró el archivo Cap200d.csv")
        
        if file_cap200e and os.path.exists(file_cap200e):
            df_costo = read_csv_with_encoding(file_cap200e)
        else:
            df_costo = pd.DataFrame()
            logger.warning("No se encontró el archivo Cap200e.csv")
        
        # Obtener conexión a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Procesar los datos
        count = 0
        sample_size = min(100, len(df_agricola))  # Limitar a 100 registros para una demostración rápida
        sample_data = df_agricola.sample(sample_size) if len(df_agricola) > 100 else df_agricola
        
        # Buscar columnas clave en los datos
        col_codigo = next((col for col in df_agricola.columns if 'CODIGO' in col), None)
        col_ccdd = next((col for col in df_agricola.columns if 'CCDD' in col), None)
        col_ccpp = next((col for col in df_agricola.columns if 'CCPP' in col), None)
        col_ccdi = next((col for col in df_agricola.columns if 'CCDI' in col), None)
        col_cultivo_cod = next((col for col in df_agricola.columns if 'P204_COD' in col), None)
        col_superficie = next((col for col in df_agricola.columns if 'P218A' in col or 'SUPERFICIE' in col), None)
        
        if not all([col_codigo, col_ccdd, col_ccpp, col_ccdi]):
            logger.warning(f"Columnas esenciales no encontradas: CODIGO, CCDD, CCPP, CCDI. Usando índices como referencia.")
        
        for idx, row in sample_data.iterrows():
            # Cada 10 registros mostrar progreso
            if count % 10 == 0:
                logger.info(f"Procesando registro agrícola {count}/{sample_size}")
                
            # Generar un código único para este productor basado en CODIGO original o índice
            if col_codigo and pd.notna(row[col_codigo]):
                codigo = f"{row[col_codigo]}_{idx}"
            else:
                codigo = f"PROD_{idx}"
            
            # Buscar datos complementarios
            if not df_cosecha.empty and col_codigo and col_codigo in df_cosecha and col_codigo in row:
                cosecha_rows = df_cosecha[df_cosecha[col_codigo] == row[col_codigo]]
                cosecha_row = cosecha_rows.iloc[0] if not cosecha_rows.empty else {}
            else:
                cosecha_row = {}
                
            if not df_destino.empty and col_codigo and col_codigo in df_destino and col_codigo in row:
                destino_rows = df_destino[df_destino[col_codigo] == row[col_codigo]]
                destino_row = destino_rows.iloc[0] if not destino_rows.empty else {}
            else:
                destino_row = {}
                
            if not df_costo.empty and col_codigo and col_codigo in df_costo and col_codigo in row:
                costo_rows = df_costo[df_costo[col_codigo] == row[col_codigo]]
                costo_row = costo_rows.iloc[0] if not costo_rows.empty else {}
            else:
                costo_row = {}
            
            # Valores a insertar
            ccdd = str(row[col_ccdd]) if col_ccdd and col_ccdd in row and pd.notna(row[col_ccdd]) else '01'
            ccpp = str(row[col_ccpp]) if col_ccpp and col_ccpp in row and pd.notna(row[col_ccpp]) else '01'
            ccdi = str(row[col_ccdi]) if col_ccdi and col_ccdi in row and pd.notna(row[col_ccdi]) else '01'
            
            # Valores numéricos con manejo de errores
            def safe_float(value):
                try:
                    if pd.isna(value):
                        return 0
                    return float(value)
                except:
                    return 0
            
            cultivo_cod = str(row[col_cultivo_cod]) if col_cultivo_cod and col_cultivo_cod in row and pd.notna(row[col_cultivo_cod]) else 'C001'
            superficie_sembrada = safe_float(row.get(col_superficie, 0))
            superficie_cosechada = safe_float(row.get('P218B', 0))
            produccion = safe_float(cosecha_row.get('P222', 0) if isinstance(cosecha_row, pd.Series) else 0)
            rendimiento = safe_float(cosecha_row.get('P223', 0) if isinstance(cosecha_row, pd.Series) else 0)
            destino_venta = safe_float(destino_row.get('P227_1', 0) if isinstance(destino_row, pd.Series) else 0)
            destino_autoconsumo = safe_float(destino_row.get('P227_2', 0) if isinstance(destino_row, pd.Series) else 0)
            costo_semillas = safe_float(costo_row.get('P232_1', 0) if isinstance(costo_row, pd.Series) else 0)
            costo_fertilizantes = safe_float(costo_row.get('P232_2', 0) if isinstance(costo_row, pd.Series) else 0)
            costo_plaguicidas = safe_float(costo_row.get('P232_3', 0) if isinstance(costo_row, pd.Series) else 0)
            costo_total = safe_float(costo_row.get('P232_T', 0) if isinstance(costo_row, pd.Series) else 0)
            
            # Obtener IDs de dimensiones
            # Ubicación
            cursor.execute(
                "SELECT id_ubicacion FROM ena.dim_ubicacion WHERE ccdd = %s AND ccpp = %s AND ccdi = %s",
                (ccdd, ccpp, ccdi)
            )
            result = cursor.fetchone()
            if result:
                id_ubicacion = result[0]
            else:
                # Si no existe, insertar nuevo registro
                cursor.execute(
                    "INSERT INTO ena.dim_ubicacion (ccdd, ccpp, ccdi) VALUES (%s, %s, %s) RETURNING id_ubicacion",
                    (ccdd, ccpp, ccdi)
                )
                id_ubicacion = cursor.fetchone()[0]
            
            # Productor
            cursor.execute(
                "SELECT id_productor FROM ena.dim_productor WHERE codigo = %s",
                (codigo,)
            )
            result = cursor.fetchone()
            if result:
                id_productor = result[0]
            else:
                # Si no existe, insertar nuevo registro
                cursor.execute(
                    "INSERT INTO ena.dim_productor (codigo) VALUES (%s) RETURNING id_productor",
                    (codigo,)
                )
                id_productor = cursor.fetchone()[0]
            
            # Cultivo
            cursor.execute(
                "SELECT id_cultivo FROM ena.dim_cultivo WHERE p204_cod = %s",
                (cultivo_cod,)
            )
            result = cursor.fetchone()
            if result:
                id_cultivo = result[0]
            else:
                # Si no existe, insertar nuevo registro con valores predeterminados
                cultivo_nom = row.get('P204_NOM', 'No especificado') if 'P204_NOM' in row else 'No especificado'
                cultivo_tipo = row.get('P204_TIPO', 'No especificado') if 'P204_TIPO' in row else 'No especificado'
                
                cursor.execute(
                    "INSERT INTO ena.dim_cultivo (p204_cod, p204_nom, p204_tipo) VALUES (%s, %s, %s) RETURNING id_cultivo",
                    (cultivo_cod, cultivo_nom, cultivo_tipo)
                )
                id_cultivo = cursor.fetchone()[0]
            
            # Tiempo (fijo para 2021)
            cursor.execute("SELECT id_tiempo FROM ena.dim_tiempo WHERE anio = 2021")
            result = cursor.fetchone()
            if result:
                id_tiempo = result[0]
            else:
                cursor.execute(
                    "INSERT INTO ena.dim_tiempo (anio, trimestre, mes) VALUES (2021, 0, 0) RETURNING id_tiempo"
                )
                id_tiempo = cursor.fetchone()[0]
            
            # Tecnología (tomar el primero disponible o crear uno nuevo)
            cursor.execute("SELECT id_tecnologia FROM ena.dim_tecnologia LIMIT 1")
            result = cursor.fetchone()
            if result:
                id_tecnologia = result[0]
            else:
                cursor.execute(
                    """
                    INSERT INTO ena.dim_tecnologia 
                    (usa_fertilizantes, tipo_fertilizante, tiene_analisis_suelo, practica_conservacion, tipo_riego, fuente_agua) 
                    VALUES (false, 'Desconocido', false, false, 'Sin riego', 'Ninguna') 
                    RETURNING id_tecnologia
                    """
                )
                id_tecnologia = cursor.fetchone()[0]
            
            # Insertar en la tabla de hechos
            try:
                cursor.execute(
                    """
                    INSERT INTO ena.fact_produccion_agricola 
                    (id_ubicacion, id_productor, id_cultivo, id_tiempo, id_tecnologia,
                     superficie_sembrada, superficie_cosechada, produccion_total, rendimiento,
                     costo_semillas, costo_fertilizantes, costo_plaguicidas, costo_total,
                     destino_venta, destino_autoconsumo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        id_ubicacion, id_productor, id_cultivo, id_tiempo, id_tecnologia,
                        superficie_sembrada, superficie_cosechada, produccion, rendimiento,
                        costo_semillas, costo_fertilizantes, costo_plaguicidas, costo_total,
                        destino_venta, destino_autoconsumo
                    )
                )
                conn.commit()
                count += 1
            except Exception as e:
                conn.rollback()
                logger.warning(f"Error al insertar registro {count}: {e}")
        
        cursor.close()
        conn.close()
        
        logger.info(f"Carga de datos agrícolas completada. {count} registros insertados.")
        return True
        
    except Exception as e:
        logger.error(f"Error en la carga de datos agrícolas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def create_views():
    """Crear vistas para facilitar reportes"""
    try:
        logger.info("Creando vistas para reportes...")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Vista para reporte de producción agrícola por departamento
        cursor.execute("""
        CREATE OR REPLACE VIEW ena.v_produccion_agricola_departamento AS
        SELECT 
            u.nombredd AS departamento,
            c.p204_nom AS cultivo,
            c.p204_tipo AS tipo_cultivo,
            SUM(f.superficie_sembrada) AS superficie_sembrada,
            SUM(f.superficie_cosechada) AS superficie_cosechada,
            SUM(f.produccion_total) AS produccion_total,
            CASE 
                WHEN SUM(f.superficie_cosechada) > 0 THEN SUM(f.produccion_total) / SUM(f.superficie_cosechada)
                ELSE 0
            END AS rendimiento_ha
        FROM 
            ena.fact_produccion_agricola f
        JOIN 
            ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
        JOIN 
            ena.dim_cultivo c ON f.id_cultivo = c.id_cultivo
        GROUP BY 
            u.nombredd, c.p204_nom, c.p204_tipo
        """)
        
        # Vista para reporte de tecnificación por departamento
        cursor.execute("""
        CREATE OR REPLACE VIEW ena.v_tecnificacion_departamento AS
        SELECT 
            u.nombredd AS departamento,
            COUNT(DISTINCT f.id_productor) AS total_productores,
            SUM(CASE WHEN t.usa_fertilizantes THEN 1 ELSE 0 END) AS productores_con_fertilizantes,
            SUM(CASE WHEN t.tiene_analisis_suelo THEN 1 ELSE 0 END) AS productores_con_analisis_suelo,
            SUM(CASE WHEN t.practica_conservacion THEN 1 ELSE 0 END) AS productores_con_conservacion,
            SUM(CASE WHEN t.tipo_riego IN ('Aspersión', 'Goteo', 'Microaspersión') THEN 1 ELSE 0 END) AS productores_riego_tecnificado
        FROM 
            ena.fact_produccion_agricola f
        JOIN 
            ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
        JOIN 
            ena.dim_tecnologia t ON f.id_tecnologia = t.id_tecnologia
        GROUP BY 
            u.nombredd
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Vistas creadas exitosamente")
        return True
    except Exception as e:
        logger.error(f"Error al crear vistas: {e}")
        return False

def main():
    """Función principal para cargar todos los datos"""
    try:
        logger.info("Iniciando carga de datos de la ENA 2021")
        
        # Asegurar que el paquete chardet esté instalado
        try:
            import chardet
        except ImportError:
            logger.info("Instalando dependencia chardet...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "chardet"])
            import chardet
        
        # Esperar a que PostgreSQL esté disponible
        logger.info("Esperando a que PostgreSQL esté disponible...")
        time.sleep(15)
        
        # Verificar existencia del esquema y crearlo si es necesario
        if not ensure_schema_exists():
            logger.error("No se pudo crear el esquema. Abortando.")
            return False
        
        # Verificar existencia de las tablas y crearlas si es necesario
        if not ensure_tables_exist():
            logger.error("No se pudieron crear las tablas. Abortando.")
            return False
        
        # Limpiar datos existentes para evitar conflictos
        if not clear_existing_data():
            logger.error("No se pudieron limpiar los datos existentes. Continuando con precaución.")
        
        # Verificar que el directorio de datos existe
        if not os.path.isdir(DATA_DIR):
            logger.error(f"Directorio de datos no encontrado: {DATA_DIR}")
            return False
        
        # Listar archivos disponibles
        logger.info(f"Archivos disponibles en {DATA_DIR}:")
        files = os.listdir(DATA_DIR)
        for file in files:
            logger.info(f"  - {file}")
        
        # Cargar dimensiones
        if load_dimension_data():
            logger.info("Dimensiones cargadas correctamente")
            
            # Cargar datos agrícolas
            if load_agricultural_data():
                logger.info("Datos agrícolas cargados correctamente")
            else:
                logger.error("Error al cargar datos agrícolas")
            
            # Crear vistas para reportes
            if create_views():
                logger.info("Vistas creadas correctamente")
            else:
                logger.error("Error al crear vistas")
            
            logger.info("Proceso de carga de datos completado")
            return True
        else:
            logger.error("Error al cargar dimensiones")
            return False
        
    except Exception as e:
        logger.error(f"Error en el proceso principal: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        logger.info("Proceso de carga finalizado.")
        logger.info("Puedes acceder a pgAdmin en http://localhost:5050 para visualizar los datos.")
        logger.info("Credenciales de pgAdmin:")
        logger.info("  Email: admin@admin.com")
        logger.info("  Password: admin")

if __name__ == "__main__":
    main()