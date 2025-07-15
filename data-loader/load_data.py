#!/usr/bin/env python3
"""
Script optimizado para carga de datos de la ENA 2021 en PostgreSQL.
"""

import os, pandas as pd, psycopg2, logging, time, glob, chardet
from psycopg2 import extras
import hashlib

# Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'ena_database')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'postgres')
DATA_DIR = os.environ.get('DATA_DIR', '/data')
BATCH_SIZE = 1000

def detect_encoding(file_path):
    try:
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read(10000))
        logger.info(f"Codificación para {os.path.basename(file_path)}: {result['encoding']}")
        return result['encoding'] or 'latin1'
    except: 
        return 'latin1'

def read_csv_with_encoding(file_path):
    encodings = [detect_encoding(file_path), 'utf-8', 'latin1', 'cp1252']
    
    for encoding in encodings:
        try:
            logger.info(f"Intentando leer {file_path} con codificación {encoding}")
            df = pd.read_csv(file_path, encoding=encoding, dtype={'CCDD': str, 'CCPP': str, 'CCDI': str, 
                                                                  'CONGLOMERADO': str, 'CODIGO': str})
            logger.info(f"Archivo {file_path} leído: {len(df)} filas, {len(df.columns)} columnas")
            return df
        except UnicodeDecodeError:
            logger.warning(f"Error de codificación con {encoding}")
        except Exception as e:
            logger.warning(f"Error al leer con {encoding}: {e}")
    
    # Último intento con manejo de errores
    return pd.read_csv(file_path, encoding='latin1', errors='replace')

def get_db_connection():
    retry_count = 0
    while retry_count < 10:
        try:
            conn = psycopg2.connect(
                host=POSTGRES_HOST, database=POSTGRES_DB,
                user=POSTGRES_USER, password=POSTGRES_PASSWORD
            )
            logger.info("Conexión a PostgreSQL exitosa")
            return conn
        except Exception as e:
            retry_count += 1
            logger.warning(f"Intento {retry_count}/10 falló: {e}")
            time.sleep(5)
    raise Exception("No se pudo conectar a PostgreSQL después de 10 intentos")

def ensure_schema_exists():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE SCHEMA IF NOT EXISTS ena")
    conn.commit()
    cursor.close()
    conn.close()
    return True

def clear_existing_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SET session_replication_role = 'replica'")
    
    tables = ["fact_produccion_agricola", "fact_produccion_pecuaria", "fact_servicios",
              "dim_ubicacion", "dim_productor", "dim_cultivo", "dim_animal", 
              "dim_tiempo", "dim_tecnologia"]
    
    for table in tables:
        cursor.execute(f"TRUNCATE ena.{table} CASCADE")
    
    cursor.execute("SET session_replication_role = 'origin'")
    conn.commit()
    cursor.close()
    conn.close()
    return True

def ensure_tables_exist():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verificar si existe la tabla principal
    cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'ena' AND table_name = 'dim_ubicacion')")
    if not cursor.fetchone()[0]:
        # Crear tablas dimensionales
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.dim_ubicacion (
            id_ubicacion SERIAL PRIMARY KEY,
            anio INTEGER,
            ccdd VARCHAR(2),
            nombredd VARCHAR(100),
            ccpp VARCHAR(2),
            nombrepv VARCHAR(100),
            ccdi VARCHAR(2),
            nombredi VARCHAR(100),
            conglomerado VARCHAR(10),
            region VARCHAR(50),
            dominio VARCHAR(50),
            area VARCHAR(20),
            altitud NUMERIC(8,2),
            UNIQUE(ccdd, ccpp, ccdi, conglomerado)
        )""")
        
        cursor.execute("CREATE INDEX idx_dim_ubicacion_ccdd ON ena.dim_ubicacion(ccdd)")
        cursor.execute("CREATE INDEX idx_dim_ubicacion_region ON ena.dim_ubicacion(region)")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.dim_productor (
            id_productor SERIAL PRIMARY KEY,
            codigo VARCHAR(20),
            conglomerado VARCHAR(10),
            nselua VARCHAR(10),
            ua VARCHAR(10),
            p101a VARCHAR(100),
            p102_1 INTEGER,
            p102_2 INTEGER,
            p102_3 INTEGER,
            sexo VARCHAR(1),
            edad INTEGER,
            nivel_educativo VARCHAR(100),
            experiencia INTEGER,
            pertenece_organizacion BOOLEAN,
            tipo_organizacion VARCHAR(50),
            UNIQUE(codigo, conglomerado, nselua, ua)
        )""")
        
        cursor.execute("CREATE INDEX idx_dim_productor_codigo ON ena.dim_productor(codigo)")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.dim_cultivo (
            id_cultivo SERIAL PRIMARY KEY,
            codigo VARCHAR(10),
            nombre VARCHAR(200),
            tipo VARCHAR(100),
            categoria VARCHAR(50),
            uso_semilla_certificada BOOLEAN,
            UNIQUE(codigo)
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.dim_animal (
            id_animal SERIAL PRIMARY KEY,
            codigo VARCHAR(10),
            nombre VARCHAR(100),
            tipo VARCHAR(50),
            raza BOOLEAN,
            UNIQUE(codigo)
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.dim_tiempo (
            id_tiempo SERIAL PRIMARY KEY,
            anio INTEGER,
            mes INTEGER,
            trimestre INTEGER,
            UNIQUE(anio, mes, trimestre)
        )""")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.dim_tecnologia (
            id_tecnologia SERIAL PRIMARY KEY,
            realizo_analisis_suelo BOOLEAN,
            recibio_asistencia_analisis BOOLEAN,
            aplica_conservacion_suelos BOOLEAN,
            usa_fertilizantes BOOLEAN,
            usa_abonos_organicos BOOLEAN,
            realiza_practicas_fertilizacion BOOLEAN,
            usa_plaguicidas BOOLEAN,
            aplica_manejo_plagas BOOLEAN,
            cuenta_sistema_riego BOOLEAN,
            tipo_sistema_riego VARCHAR(50),
            riego_tecnificado BOOLEAN
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
            factor DECIMAL(12,6),
            superficie_sembrada DECIMAL(12,2),
            superficie_cosechada DECIMAL(12,2),
            produccion_total DECIMAL(12,2),
            rendimiento DECIMAL(12,2),
            precio_chacra DECIMAL(12,2),
            costo_semillas DECIMAL(12,2),
            costo_fertilizantes DECIMAL(12,2),
            costo_plaguicidas DECIMAL(12,2),
            costo_total DECIMAL(12,2),
            destino_venta DECIMAL(12,2),
            destino_autoconsumo DECIMAL(12,2),
            orientacion_siembras BOOLEAN
        )""")
        
        cursor.execute("CREATE INDEX idx_fact_agricola_ubicacion ON ena.fact_produccion_agricola(id_ubicacion)")
        cursor.execute("CREATE INDEX idx_fact_agricola_productor ON ena.fact_produccion_agricola(id_productor)")
        cursor.execute("CREATE INDEX idx_fact_agricola_cultivo ON ena.fact_produccion_agricola(id_cultivo)")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.fact_produccion_pecuaria (
            id_produccion SERIAL PRIMARY KEY,
            id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
            id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
            id_animal INTEGER REFERENCES ena.dim_animal(id_animal),
            id_tiempo INTEGER REFERENCES ena.dim_tiempo(id_tiempo),
            factor DECIMAL(12,6),
            numero_animales INTEGER,
            produccion_leche DECIMAL(12,2),
            produccion_huevos DECIMAL(12,2),
            produccion_carne DECIMAL(12,2),
            costo_total DECIMAL(12,2),
            uso_reproductores_calidad BOOLEAN
        )""")
        
        cursor.execute("CREATE INDEX idx_fact_pecuaria_ubicacion ON ena.fact_produccion_pecuaria(id_ubicacion)")
        cursor.execute("CREATE INDEX idx_fact_pecuaria_productor ON ena.fact_produccion_pecuaria(id_productor)")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ena.fact_servicios (
            id_servicio SERIAL PRIMARY KEY,
            id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
            id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
            id_tiempo INTEGER REFERENCES ena.dim_tiempo(id_tiempo),
            recibe_capacitacion BOOLEAN,
            recibe_asistencia_tecnica BOOLEAN,
            usa_servicio_informacion BOOLEAN,
            es_organizado BOOLEAN,
            acceso_credito BOOLEAN
        )""")
        
        cursor.execute("CREATE INDEX idx_servicios_productor ON ena.fact_servicios(id_productor)")
        cursor.execute("CREATE INDEX idx_servicios_ubicacion ON ena.fact_servicios(id_ubicacion)")
        
        logger.info("Tablas creadas exitosamente")
    
    conn.commit()
    cursor.close()
    conn.close()
    return True

def find_files(pattern):
    return glob.glob(os.path.join(DATA_DIR, pattern))

def safe_float(value):
    try:
        if pd.isna(value):
            return 0
        return float(value)
    except:
        return 0

def safe_bool(value):
    try:
        if pd.isna(value):
            return False
        return bool(int(value) == 1)
    except:
        return False

def load_dimension_data():
    # Buscar archivos
    file_cap100_1 = find_files("*Cap100_1*.csv")
    file_cap200a = find_files("*Cap200a*.csv") + find_files("*Cap200ab*.csv")
    file_cap300ab = find_files("*Cap300ab*.csv")
    
    if not file_cap100_1:
        logger.error("No se encontró archivo Cap100_1")
        return False
        
    # Usar el primer archivo encontrado
    file_cap100_1 = file_cap100_1[0]
    file_cap200a = file_cap200a[0] if file_cap200a else None
    file_cap300ab = file_cap300ab[0] if file_cap300ab else None
    
    # Crear dimensión tiempo
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Cargar dim_tiempo
    logger.info("Cargando dimensión tiempo...")
    for mes in range(1, 13):
        trimestre = (mes-1) // 3 + 1
        cursor.execute(
            "INSERT INTO ena.dim_tiempo (anio, mes, trimestre) VALUES (%s, %s, %s)",
            (2021, mes, trimestre)
        )
    
    # Cargar dim_ubicacion desde Cap100_1
    logger.info(f"Cargando ubicaciones desde {file_cap100_1}")
    df_ubicacion = read_csv_with_encoding(file_cap100_1)
    
    # Insertar ubicaciones únicas
    ubicaciones = []
    for _, row in df_ubicacion.iterrows():
        if all(col in df_ubicacion.columns for col in ['CCDD', 'CCPP', 'CCDI']):
            ccdd = str(row['CCDD']).zfill(2)
            ccpp = str(row['CCPP']).zfill(2)
            ccdi = str(row['CCDI']).zfill(2)
            conglomerado = str(row['CONGLOMERADO']).zfill(5) if 'CONGLOMERADO' in row and pd.notna(row['CONGLOMERADO']) else '00000'
            nombredd = str(row['NOMBREDD']) if 'NOMBREDD' in row and pd.notna(row['NOMBREDD']) else 'Sin Datos'
            nombrepv = str(row['NOMBREPV']) if 'NOMBREPV' in row and pd.notna(row['NOMBREPV']) else 'Sin Datos'
            nombredi = str(row['NOMBREDI']) if 'NOMBREDI' in row and pd.notna(row['NOMBREDI']) else 'Sin Datos'
            region = str(row['REGION']) if 'REGION' in row and pd.notna(row['REGION']) else 'Sin Datos'
            
            # Verificar si ya existe en la lista
            key = (ccdd, ccpp, ccdi, conglomerado)
            if key not in [x[:4] for x in ubicaciones]:
                ubicaciones.append((ccdd, ccpp, ccdi, conglomerado, nombredd, nombrepv, nombredi, region))
    
    # Insertar por lotes
    for i in range(0, len(ubicaciones), BATCH_SIZE):
        batch = ubicaciones[i:i+BATCH_SIZE]
        extras.execute_batch(
            cursor,
            """
            INSERT INTO ena.dim_ubicacion 
            (ccdd, ccpp, ccdi, conglomerado, nombredd, nombrepv, nombredi, region, anio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 2021)
            ON CONFLICT (ccdd, ccpp, ccdi, conglomerado) DO NOTHING
            """,
            [(u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7]) for u in batch]
        )
    
    logger.info(f"Insertadas {len(ubicaciones)} ubicaciones únicas")
    
    # Cargar dim_productor desde Cap100_1
    logger.info("Cargando productores...")
    productores = []
    for _, row in df_ubicacion.iterrows():
        if 'CODIGO' in df_ubicacion.columns:
            codigo = str(row['CODIGO']) if pd.notna(row['CODIGO']) else f"PROD_{_}"
            conglomerado = str(row['CONGLOMERADO']).zfill(5) if 'CONGLOMERADO' in row and pd.notna(row['CONGLOMERADO']) else '00000'
            nselua = str(row['NSELUA']) if 'NSELUA' in row and pd.notna(row['NSELUA']) else ''
            ua = str(row['UA']) if 'UA' in row and pd.notna(row['UA']) else ''
            
            p102_1 = safe_float(row['P102_1']) if 'P102_1' in row else None
            p102_2 = safe_float(row['P102_2']) if 'P102_2' in row else None
            p102_3 = safe_float(row['P102_3']) if 'P102_3' in row else None
            
            # Verificar si ya existe en la lista
            key = (codigo, conglomerado, nselua, ua)
            if key not in [x[:4] for x in productores]:
                productores.append((codigo, conglomerado, nselua, ua, p102_1, p102_2, p102_3))
    
    # Insertar por lotes
    for i in range(0, len(productores), BATCH_SIZE):
        batch = productores[i:i+BATCH_SIZE]
        extras.execute_batch(
            cursor,
            """
            INSERT INTO ena.dim_productor 
            (codigo, conglomerado, nselua, ua, p102_1, p102_2, p102_3)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (codigo, conglomerado, nselua, ua) DO NOTHING
            """,
            batch
        )
    
    logger.info(f"Insertados {len(productores)} productores únicos")
    
    # Cargar dim_cultivo desde Cap200a si existe
    cultivos = []
    if file_cap200a:
        logger.info(f"Cargando cultivos desde {file_cap200a}")
        df_cultivo = read_csv_with_encoding(file_cap200a)
        
        # Buscar columnas de código y nombre de cultivo
        col_cod = next((col for col in df_cultivo.columns if 'P204_COD' in col or 'COD' in col), None)
        col_nom = next((col for col in df_cultivo.columns if 'P204_NOM' in col or 'NOM' in col), None)
        col_tipo = next((col for col in df_cultivo.columns if 'P204_TIPO' in col or 'TIPO' in col), None)
        
        if col_cod:
            for _, row in df_cultivo.iterrows():
                if pd.notna(row[col_cod]):
                    codigo = str(row[col_cod])
                    nombre = str(row[col_nom]) if col_nom and pd.notna(row[col_nom]) else 'No especificado'
                    tipo = str(row[col_tipo]) if col_tipo and pd.notna(row[col_tipo]) else 'No especificado'
                    
                    # Verificar si ya existe
                    if codigo not in [c[0] for c in cultivos]:
                        cultivos.append((codigo, nombre, tipo, tipo, False))
    
    # Si no hay cultivos, crear algunos básicos
    if not cultivos:
        cultivos = [
            ('01', 'PAPA', 'TUBERCULO', 'TUBERCULO', False),
            ('02', 'MAIZ', 'CEREAL', 'CEREAL', False),
            ('03', 'ARROZ', 'CEREAL', 'CEREAL', False),
            ('04', 'TRIGO', 'CEREAL', 'CEREAL', False),
            ('05', 'FRIJOL', 'MENESTRA', 'MENESTRA', False)
        ]
    
    # Insertar cultivos
    for i in range(0, len(cultivos), BATCH_SIZE):
        batch = cultivos[i:i+BATCH_SIZE]
        extras.execute_batch(
            cursor,
            """
            INSERT INTO ena.dim_cultivo 
            (codigo, nombre, tipo, categoria, uso_semilla_certificada)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (codigo) DO NOTHING
            """,
            batch
        )
    
    logger.info(f"Insertados {len(cultivos)} cultivos únicos")
    
    # Cargar dim_animal
    animales = []
    if file_cap300ab:
        logger.info(f"Cargando animales desde {file_cap300ab}")
        df_animal = read_csv_with_encoding(file_cap300ab)
        
        # Buscar columnas relacionadas con animales
        animal_cols = [col for col in df_animal.columns if 'P301' in col and 'COD' in col]
        
        if animal_cols:
            for _, row in df_animal.iterrows():
                for col in animal_cols:
                    if pd.notna(row[col]):
                        codigo = str(row[col]).strip()
                        nombre_col = col.replace('COD', 'NOM')
                        nombre = str(row[nombre_col]) if nombre_col in row and pd.notna(row[nombre_col]) else f"ANIMAL_{codigo}"
                        
                        if codigo and codigo not in [a[0] for a in animales]:
                            animales.append((codigo, nombre, 'PRINCIPAL', False))
    
    # Si no hay animales, crear algunos básicos
    if not animales:
        animales = [
            ('01', 'VACUNO', 'PRINCIPAL', False),
            ('02', 'OVINO', 'PRINCIPAL', False),
            ('03', 'PORCINO', 'PRINCIPAL', False),
            ('07', 'AVES', 'PRINCIPAL', False)
        ]
    
    # Insertar animales
    for i in range(0, len(animales), BATCH_SIZE):
        batch = animales[i:i+BATCH_SIZE]
        extras.execute_batch(
            cursor,
            """
            INSERT INTO ena.dim_animal
            (codigo, nombre, tipo, raza)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (codigo) DO NOTHING
            """,
            batch
        )
    
    logger.info(f"Insertados {len(animales)} animales únicos")
    
    # Cargar dim_tecnologia (perfiles genéricos)
    tecnologias = [
        (True, True, True, True, True, True, True, True, True, 'Aspersión', True),
        (True, False, True, False, True, False, True, False, True, 'Goteo', True),
        (False, False, False, True, True, True, False, False, True, 'Gravedad', False),
        (False, False, False, False, False, False, False, False, False, 'Ninguno', False)
    ]
    
    cursor.executemany(
        """
        INSERT INTO ena.dim_tecnologia
        (realizo_analisis_suelo, recibio_asistencia_analisis, aplica_conservacion_suelos,
         usa_fertilizantes, usa_abonos_organicos, realiza_practicas_fertilizacion,
         usa_plaguicidas, aplica_manejo_plagas, cuenta_sistema_riego,
         tipo_sistema_riego, riego_tecnificado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        tecnologias
    )
    
    logger.info(f"Insertados {len(tecnologias)} perfiles de tecnología")
    
    conn.commit()
    cursor.close()
    conn.close()
    return True

def load_agricultural_data():
    # Buscar archivos
    file_cap200a = find_files("*Cap200a*.csv") + find_files("*Cap200ab*.csv")
    file_cap200c = find_files("*Cap200c*.csv")
    file_cap200d = find_files("*Cap200d*.csv")
    
    if not file_cap200a:
        logger.error("Archivo de cultivos no encontrado")
        return False
    
    file_cap200a = file_cap200a[0]
    file_cap200c = file_cap200c[0] if file_cap200c else None
    file_cap200d = file_cap200d[0] if file_cap200d else None
    
    # Leer datos
    df_agricola = read_csv_with_encoding(file_cap200a)
    df_cosecha = pd.DataFrame() if not file_cap200c else read_csv_with_encoding(file_cap200c)
    df_destino = pd.DataFrame() if not file_cap200d else read_csv_with_encoding(file_cap200d)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Precarga de IDs
    logger.info("Precargando mapeo de dimensiones...")
    
    # Obtener id_tiempo (año 2021)
    cursor.execute("SELECT id_tiempo FROM ena.dim_tiempo WHERE anio = 2021 AND mes = 1")
    id_tiempo = cursor.fetchone()[0]
    
    # Mapeo de ubicaciones
    ubicacion_map = {}
    cursor.execute("SELECT id_ubicacion, ccdd, ccpp, ccdi, conglomerado FROM ena.dim_ubicacion")
    for row in cursor.fetchall():
        key = f"{row[1]}_{row[2]}_{row[3]}_{row[4]}"
        ubicacion_map[key] = row[0]
    
    # Mapeo de productores
    productor_map = {}
    cursor.execute("SELECT id_productor, codigo, conglomerado FROM ena.dim_productor")
    for row in cursor.fetchall():
        key = f"{row[1]}_{row[2]}"
        productor_map[key] = row[0]
    
    # Mapeo de cultivos
    cultivo_map = {}
    cursor.execute("SELECT id_cultivo, codigo FROM ena.dim_cultivo")
    for row in cursor.fetchall():
        cultivo_map[row[1]] = row[0]
    
    # Tecnologías disponibles
    cursor.execute("SELECT id_tecnologia FROM ena.dim_tecnologia")
    tecnologia_ids = [row[0] for row in cursor.fetchall()]
    
    # Identificar columnas clave
    col_codigo = next((col for col in df_agricola.columns if col == 'CODIGO'), None)
    col_ccdd = next((col for col in df_agricola.columns if col == 'CCDD'), None)
    col_ccpp = next((col for col in df_agricola.columns if col == 'CCPP'), None)
    col_ccdi = next((col for col in df_agricola.columns if col == 'CCDI'), None)
    col_conglomerado = next((col for col in df_agricola.columns if col == 'CONGLOMERADO'), None)
    col_cultivo_cod = next((col for col in df_agricola.columns if 'P204_COD' in col), None)
    col_superficie = next((col for col in df_agricola.columns if 'P218A' in col or 'SUPERFICIE' in col), None)
    
    # Procesar datos
    batch_data = []
    count = 0
    total = len(df_agricola)
    
    logger.info(f"Procesando {total} registros agrícolas...")
    
    for idx, row in df_agricola.iterrows():
        if count % 1000 == 0:
            logger.info(f"Procesando {count}/{total} ({count/total*100:.1f}%)")
        
        try:
            # Datos básicos
            codigo = str(row[col_codigo]) if col_codigo and pd.notna(row[col_codigo]) else f"PROD_{idx}"
            ccdd = str(row[col_ccdd]).zfill(2) if col_ccdd and pd.notna(row[col_ccdd]) else '00'
            ccpp = str(row[col_ccpp]).zfill(2) if col_ccpp and pd.notna(row[col_ccpp]) else '00'
            ccdi = str(row[col_ccdi]).zfill(2) if col_ccdi and pd.notna(row[col_ccdi]) else '00'
            conglomerado = str(row[col_conglomerado]).zfill(5) if col_conglomerado and pd.notna(row[col_conglomerado]) else '00000'
            
            # Buscar datos complementarios
            cosecha_row = pd.Series()
            if not df_cosecha.empty and col_codigo and col_codigo in df_cosecha.columns:
                cosecha_rows = df_cosecha[df_cosecha[col_codigo] == row[col_codigo]]
                if not cosecha_rows.empty:
                    cosecha_row = cosecha_rows.iloc[0]
            
            destino_row = pd.Series()
            if not df_destino.empty and col_codigo and col_codigo in df_destino.columns:
                destino_rows = df_destino[df_destino[col_codigo] == row[col_codigo]]
                if not destino_rows.empty:
                    destino_row = destino_rows.iloc[0]
            
            # Extraer datos agrícolas
            cultivo_cod = str(row[col_cultivo_cod]) if col_cultivo_cod and pd.notna(row[col_cultivo_cod]) else '01'
            superficie_sembrada = safe_float(row.get(col_superficie, 0))
            superficie_cosechada = safe_float(row.get('P218B', 0)) if 'P218B' in row else 0
            
            produccion = safe_float(cosecha_row.get('P222', 0)) if 'P222' in cosecha_row else 0
            rendimiento = safe_float(cosecha_row.get('P223', 0)) if 'P223' in cosecha_row else 0
            precio_chacra = safe_float(cosecha_row.get('P224', 0)) if 'P224' in cosecha_row else 0
            
            destino_venta = safe_float(destino_row.get('P227_1', 0)) if 'P227_1' in destino_row else 0
            destino_autoconsumo = safe_float(destino_row.get('P227_2', 0)) if 'P227_2' in destino_row else 0
            
            costo_semillas = 0
            costo_fertilizantes = 0
            costo_plaguicidas = 0
            costo_total = 0
            
            orientacion_siembras = safe_bool(row.get('P217', 0)) if 'P217' in row else False
            
            factor = safe_float(row.get('FACTOR', 1)) if 'FACTOR' in row else 1
            
            # Obtener IDs de dimensiones
            ubicacion_key = f"{ccdd}_{ccpp}_{ccdi}_{conglomerado}"
            id_ubicacion = ubicacion_map.get(ubicacion_key)
            
            if id_ubicacion is None:
                cursor.execute(
                    "INSERT INTO ena.dim_ubicacion (ccdd, ccpp, ccdi, conglomerado, anio) VALUES (%s, %s, %s, %s, 2021) RETURNING id_ubicacion",
                    (ccdd, ccpp, ccdi, conglomerado)
                )
                id_ubicacion = cursor.fetchone()[0]
                ubicacion_map[ubicacion_key] = id_ubicacion
            
            productor_key = f"{codigo}_{conglomerado}"
            id_productor = productor_map.get(productor_key)
            
            if id_productor is None:
                cursor.execute(
                    "INSERT INTO ena.dim_productor (codigo, conglomerado) VALUES (%s, %s) RETURNING id_productor",
                    (codigo, conglomerado)
                )
                id_productor = cursor.fetchone()[0]
                productor_map[productor_key] = id_productor
            
            id_cultivo = cultivo_map.get(cultivo_cod)
            
            if id_cultivo is None:
                cultivo_nom = row.get('P204_NOM', f'CULTIVO_{cultivo_cod}') if 'P204_NOM' in row else f'CULTIVO_{cultivo_cod}'
                cultivo_tipo = row.get('P204_TIPO', 'No especificado') if 'P204_TIPO' in row else 'No especificado'
                
                cursor.execute(
                    "INSERT INTO ena.dim_cultivo (codigo, nombre, tipo) VALUES (%s, %s, %s) RETURNING id_cultivo",
                    (cultivo_cod, cultivo_nom, cultivo_tipo)
                )
                id_cultivo = cursor.fetchone()[0]
                cultivo_map[cultivo_cod] = id_cultivo
            
            # Asignar tecnología deterministicamente según hash del código
            hash_val = int(hashlib.md5(codigo.encode()).hexdigest(), 16) % len(tecnologia_ids)
            id_tecnologia = tecnologia_ids[hash_val]
            
            # Agregar al lote
            batch_data.append((
                id_ubicacion, id_productor, id_cultivo, id_tiempo, id_tecnologia,
                factor,
                superficie_sembrada, superficie_cosechada, produccion, rendimiento, precio_chacra,
                costo_semillas, costo_fertilizantes, costo_plaguicidas, costo_total,
                destino_venta, destino_autoconsumo, orientacion_siembras
            ))
            
            count += 1
            
            if len(batch_data) >= BATCH_SIZE:
                extras.execute_batch(
                    cursor,
                    """
                    INSERT INTO ena.fact_produccion_agricola (
                        id_ubicacion, id_productor, id_cultivo, id_tiempo, id_tecnologia,
                        factor,
                        superficie_sembrada, superficie_cosechada, produccion_total, rendimiento, precio_chacra,
                        costo_semillas, costo_fertilizantes, costo_plaguicidas, costo_total,
                        destino_venta, destino_autoconsumo, orientacion_siembras
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    batch_data
                )
                conn.commit()
                batch_data = []
        except Exception as e:
            logger.error(f"Error en registro {idx}: {e}")
    
    # Insertar registros restantes
    if batch_data:
        extras.execute_batch(
            cursor,
            """
            INSERT INTO ena.fact_produccion_agricola (
                id_ubicacion, id_productor, id_cultivo, id_tiempo, id_tecnologia,
                factor,
                superficie_sembrada, superficie_cosechada, produccion_total, rendimiento, precio_chacra,
                costo_semillas, costo_fertilizantes, costo_plaguicidas, costo_total,
                destino_venta, destino_autoconsumo, orientacion_siembras
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            batch_data
        )
        conn.commit()
    
    cursor.close()
    conn.close()
    logger.info(f"Datos agrícolas cargados: {count} registros")
    return True

def load_livestock_data():
    # Buscar archivos
    file_cap300ab = find_files("*Cap300ab*.csv")
    
    if not file_cap300ab:
        logger.warning("No se encontraron archivos de datos pecuarios")
        return True
    
    file_cap300ab = file_cap300ab[0]
    logger.info(f"Procesando datos pecuarios desde: {file_cap300ab}")
    
    df_pecuaria = read_csv_with_encoding(file_cap300ab)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Precarga de IDs
    cursor.execute("SELECT id_tiempo FROM ena.dim_tiempo WHERE anio = 2021 AND mes = 1")
    id_tiempo = cursor.fetchone()[0]
    
    ubicacion_map = {}
    cursor.execute("SELECT id_ubicacion, ccdd, ccpp, ccdi, conglomerado FROM ena.dim_ubicacion")
    for row in cursor.fetchall():
        key = f"{row[1]}_{row[2]}_{row[3]}_{row[4]}"
        ubicacion_map[key] = row[0]
    
    productor_map = {}
    cursor.execute("SELECT id_productor, codigo, conglomerado FROM ena.dim_productor")
    for row in cursor.fetchall():
        key = f"{row[1]}_{row[2]}"
        productor_map[key] = row[0]
    
    animal_map = {}
    cursor.execute("SELECT id_animal, codigo FROM ena.dim_animal")
    for row in cursor.fetchall():
        animal_map[row[1]] = row[0]
    
    # Identificar columnas clave
    col_codigo = next((col for col in df_pecuaria.columns if col == 'CODIGO'), None)
    col_ccdd = next((col for col in df_pecuaria.columns if col == 'CCDD'), None)
    col_ccpp = next((col for col in df_pecuaria.columns if col == 'CCPP'), None)
    col_ccdi = next((col for col in df_pecuaria.columns if col == 'CCDI'), None)
    col_conglomerado = next((col for col in df_pecuaria.columns if col == 'CONGLOMERADO'), None)
    
    # Buscar columnas de animales
    animal_cols = [col for col in df_pecuaria.columns if 'P301' in col and 'COD' in col]
    
    if not animal_cols:
        logger.warning("No se encontraron columnas de animales")
        return True
    
    # Procesar datos
    batch_data = []
    count = 0
    
    logger.info(f"Procesando {len(df_pecuaria)} registros de productores con animales")
    
    for idx, row in df_pecuaria.iterrows():
        if idx % 1000 == 0:
            logger.info(f"Procesando productor {idx}/{len(df_pecuaria)}")
        
        codigo = str(row[col_codigo]) if col_codigo and pd.notna(row[col_codigo]) else f"PROD_{idx}"
        ccdd = str(row[col_ccdd]).zfill(2) if col_ccdd and pd.notna(row[col_ccdd]) else '00'
        ccpp = str(row[col_ccpp]).zfill(2) if col_ccpp and pd.notna(row[col_ccpp]) else '00'
        ccdi = str(row[col_ccdi]).zfill(2) if col_ccdi and pd.notna(row[col_ccdi]) else '00'
        conglomerado = str(row[col_conglomerado]).zfill(5) if col_conglomerado and pd.notna(row[col_conglomerado]) else '00000'
        
        factor = safe_float(row.get('FACTOR', 1)) if 'FACTOR' in row else 1
        
        # Obtener IDs de dimensiones
        ubicacion_key = f"{ccdd}_{ccpp}_{ccdi}_{conglomerado}"
        id_ubicacion = ubicacion_map.get(ubicacion_key)
        
        if id_ubicacion is None:
            cursor.execute(
                "INSERT INTO ena.dim_ubicacion (ccdd, ccpp, ccdi, conglomerado, anio) VALUES (%s, %s, %s, %s, 2021) RETURNING id_ubicacion",
                (ccdd, ccpp, ccdi, conglomerado)
            )
            id_ubicacion = cursor.fetchone()[0]
            ubicacion_map[ubicacion_key] = id_ubicacion
        
        productor_key = f"{codigo}_{conglomerado}"
        id_productor = productor_map.get(productor_key)
        
        if id_productor is None:
            cursor.execute(
                "INSERT INTO ena.dim_productor (codigo, conglomerado) VALUES (%s, %s) RETURNING id_productor",
                (codigo, conglomerado)
            )
            id_productor = cursor.fetchone()[0]
            productor_map[productor_key] = id_productor
        
        # Procesar cada tipo de animal
        for animal_col in animal_cols:
            if pd.notna(row[animal_col]):
                animal_cod = str(row[animal_col]).strip()
                
                if not animal_cod:
                    continue
                
                # Buscar cantidad
                cantidad_col = animal_col.replace('P301', 'P302').replace('COD', 'CANT')
                numero_animales = int(safe_float(row.get(cantidad_col, 0)))
                
                if numero_animales <= 0:
                    continue
                
                # Obtener o crear animal
                id_animal = animal_map.get(animal_cod)
                
                if id_animal is None:
                    nombre_col = animal_col.replace('COD', 'NOM')
                    nombre = row.get(nombre_col, f"ANIMAL_{animal_cod}") if nombre_col in row else f"ANIMAL_{animal_cod}"
                    
                    cursor.execute(
                        "INSERT INTO ena.dim_animal (codigo, nombre, tipo, raza) VALUES (%s, %s, %s, %s) RETURNING id_animal",
                        (animal_cod, nombre, 'PRINCIPAL', False)
                    )
                    id_animal = cursor.fetchone()[0]
                    animal_map[animal_cod] = id_animal
                
                # Datos de producción específicos
                produccion_leche = 0
                produccion_huevos = 0
                produccion_carne = 0
                
                # Buscar datos de leche para vacunos
                if animal_cod in ('01', '1'):
                    leche_col = next((col for col in df_pecuaria.columns if 'P304' in col and 'CANT' in col), None)
                    if leche_col and leche_col in row:
                        produccion_leche = safe_float(row[leche_col])
                
                # Buscar datos de huevos para aves
                elif animal_cod in ('07', '7'):
                    huevos_col = next((col for col in df_pecuaria.columns if 'P305' in col and 'CANT' in col), None)
                    if huevos_col and huevos_col in row:
                        produccion_huevos = safe_float(row[huevos_col])
                
                # Reproductores de calidad
                uso_reproductores = False
                reprod_col = next((col for col in df_pecuaria.columns if 'P303' in col and animal_cod in col), None)
                if reprod_col and reprod_col in row:
                    uso_reproductores = safe_bool(row[reprod_col])
                
                # Agregar al lote
                batch_data.append((
                    id_ubicacion, id_productor, id_animal, id_tiempo,
                    factor, numero_animales,
                    produccion_leche, produccion_huevos, produccion_carne,
                    0, uso_reproductores
                ))
                
                count += 1
                
                if len(batch_data) >= BATCH_SIZE:
                    extras.execute_batch(
                        cursor,
                        """
                        INSERT INTO ena.fact_produccion_pecuaria (
                            id_ubicacion, id_productor, id_animal, id_tiempo,
                            factor, numero_animales,
                            produccion_leche, produccion_huevos, produccion_carne,
                            costo_total, uso_reproductores_calidad
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        batch_data
                    )
                    conn.commit()
                    batch_data = []
    
    # Insertar registros restantes
    if batch_data:
        extras.execute_batch(
            cursor,
            """
            INSERT INTO ena.fact_produccion_pecuaria (
                id_ubicacion, id_productor, id_animal, id_tiempo,
                factor, numero_animales,
                produccion_leche, produccion_huevos, produccion_carne,
                costo_total, uso_reproductores_calidad
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            batch_data
        )
        conn.commit()
    
    cursor.close()
    conn.close()
    logger.info(f"Datos pecuarios cargados: {count} registros")
    return True

def load_services_data():
    # Buscar archivos
    file_cap400c = find_files("*Cap400c*.csv")
    file_cap700 = find_files("*Cap700*.csv")
    
    if not file_cap400c and not file_cap700:
        logger.warning("No se encontraron archivos de servicios")
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Precarga de IDs
    cursor.execute("SELECT id_tiempo FROM ena.dim_tiempo WHERE anio = 2021 AND mes = 1")
    id_tiempo = cursor.fetchone()[0]
    
    ubicacion_map = {}
    cursor.execute("SELECT id_ubicacion, ccdd, ccpp, ccdi, conglomerado FROM ena.dim_ubicacion")
    for row in cursor.fetchall():
        key = f"{row[1]}_{row[2]}_{row[3]}_{row[4]}"
        ubicacion_map[key] = row[0]
    
    productor_map = {}
    cursor.execute("SELECT id_productor, codigo, conglomerado FROM ena.dim_productor")
    for row in cursor.fetchall():
        key = f"{row[1]}_{row[2]}"
        productor_map[key] = row[0]
    
    # Procesar datos de servicios de extensión
    count = 0
    if file_cap400c:
        file_cap400c = file_cap400c[0]
        logger.info(f"Procesando servicios de extensión desde: {file_cap400c}")
        
        df_extension = read_csv_with_encoding(file_cap400c)
        
        col_codigo = next((col for col in df_extension.columns if col == 'CODIGO'), None)
        col_conglomerado = next((col for col in df_extension.columns if col == 'CONGLOMERADO'), None)
        col_ccdd = next((col for col in df_extension.columns if col == 'CCDD'), None)
        col_ccpp = next((col for col in df_extension.columns if col == 'CCPP'), None)
        col_ccdi = next((col for col in df_extension.columns if col == 'CCDI'), None)
        
        batch_data = []
        
        for idx, row in df_extension.iterrows():
            if idx % 1000 == 0:
                logger.info(f"Procesando servicio {idx}/{len(df_extension)}")
                
            codigo = str(row[col_codigo]) if col_codigo and pd.notna(row[col_codigo]) else f"PROD_{idx}"
            ccdd = str(row[col_ccdd]).zfill(2) if col_ccdd and pd.notna(row[col_ccdd]) else '00'
            ccpp = str(row[col_ccpp]).zfill(2) if col_ccpp and pd.notna(row[col_ccpp]) else '00'
            ccdi = str(row[col_ccdi]).zfill(2) if col_ccdi and pd.notna(row[col_ccdi]) else '00'
            conglomerado = str(row[col_conglomerado]).zfill(5) if col_conglomerado and pd.notna(row[col_conglomerado]) else '00000'
            
            # Obtener IDs de dimensiones
            ubicacion_key = f"{ccdd}_{ccpp}_{ccdi}_{conglomerado}"
            id_ubicacion = ubicacion_map.get(ubicacion_key)
            
            if id_ubicacion is None:
                cursor.execute(
                    "INSERT INTO ena.dim_ubicacion (ccdd, ccpp, ccdi, conglomerado, anio) VALUES (%s, %s, %s, %s, 2021) RETURNING id_ubicacion",
                    (ccdd, ccpp, ccdi, conglomerado)
                )
                id_ubicacion = cursor.fetchone()[0]
                ubicacion_map[ubicacion_key] = id_ubicacion
            
            productor_key = f"{codigo}_{conglomerado}"
            id_productor = productor_map.get(productor_key)
            
            if id_productor is None:
                cursor.execute(
                    "INSERT INTO ena.dim_productor (codigo, conglomerado) VALUES (%s, %s) RETURNING id_productor",
                    (codigo, conglomerado)
                )
                id_productor = cursor.fetchone()[0]
                productor_map[productor_key] = id_productor
            
            # Extraer información de servicios
            recibe_capacitacion = safe_bool(row.get('P413', 0))
            recibe_asistencia_tecnica = safe_bool(row.get('P416', 0))
            usa_servicio_informacion = safe_bool(row.get('P422', 0))
            
            # Agregar al lote
            batch_data.append((
                id_productor, id_ubicacion, id_tiempo,
                recibe_capacitacion, recibe_asistencia_tecnica, usa_servicio_informacion,
                False, False
            ))
            
            count += 1
            
            if len(batch_data) >= BATCH_SIZE:
                extras.execute_batch(
                    cursor,
                    """
                    INSERT INTO ena.fact_servicios (
                        id_productor, id_ubicacion, id_tiempo,
                        recibe_capacitacion, recibe_asistencia_tecnica, usa_servicio_informacion,
                        es_organizado, acceso_credito
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    batch_data
                )
                conn.commit()
                batch_data = []
    
        # Insertar registros restantes
        if batch_data:
            extras.execute_batch(
                cursor,
                """
                INSERT INTO ena.fact_servicios (
                    id_productor, id_ubicacion, id_tiempo,
                    recibe_capacitacion, recibe_asistencia_tecnica, usa_servicio_informacion,
                    es_organizado, acceso_credito
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                batch_data
            )
            conn.commit()
    
    # Actualizar con datos de asociatividad si existen
    if file_cap700:
        file_cap700 = file_cap700[0]
        logger.info(f"Actualizando con datos de asociatividad desde: {file_cap700}")
        
        df_asociatividad = read_csv_with_encoding(file_cap700)
        
        col_codigo = next((col for col in df_asociatividad.columns if col == 'CODIGO'), None)
        col_conglomerado = next((col for col in df_asociatividad.columns if col == 'CONGLOMERADO'), None)
        
        if col_codigo:
            for idx, row in df_asociatividad.iterrows():
                if idx % 1000 == 0:
                    logger.info(f"Procesando asociatividad {idx}/{len(df_asociatividad)}")
                
                codigo = str(row[col_codigo]) if pd.notna(row[col_codigo]) else ''
                conglomerado = str(row[col_conglomerado]).zfill(5) if col_conglomerado and pd.notna(row[col_conglomerado]) else '00000'
                
                # Obtener ID del productor
                productor_key = f"{codigo}_{conglomerado}"
                id_productor = productor_map.get(productor_key)
                
                if id_productor:
                    es_organizado = safe_bool(row.get('P701', 0))
                    
                    # Actualizar registro
                    cursor.execute(
                        """
                        UPDATE ena.fact_servicios 
                        SET es_organizado = %s
                        WHERE id_productor = %s
                        """,
                        (es_organizado, id_productor)
                    )
                    conn.commit()
    
    cursor.close()
    conn.close()
    logger.info(f"Datos de servicios cargados/actualizados: {count} registros")
    return True

def create_views():
    """Crear vistas para reportes según programas presupuestales"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Vista de producción agrícola por departamento
    cursor.execute("""
    CREATE OR REPLACE VIEW ena.v_produccion_agricola_departamento AS
    SELECT 
        u.nombredd AS departamento,
        c.nombre AS cultivo,
        c.tipo AS tipo_cultivo,
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
        u.nombredd, c.nombre, c.tipo
    """)
    
    # 2. Vista de producción pecuaria
    cursor.execute("""
    CREATE OR REPLACE VIEW ena.v_produccion_pecuaria_departamento AS
    SELECT 
        u.nombredd AS departamento,
        a.nombre AS animal,
        SUM(f.numero_animales) AS total_animales,
        SUM(f.produccion_leche) AS produccion_leche,
        SUM(f.produccion_huevos) AS produccion_huevos,
        SUM(f.produccion_carne) AS produccion_carne
    FROM 
        ena.fact_produccion_pecuaria f
    JOIN 
        ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
    JOIN 
        ena.dim_animal a ON f.id_animal = a.id_animal
    GROUP BY 
        u.nombredd, a.nombre
    """)
    
    # 3. Vista de tecnificación
    cursor.execute("""
    CREATE OR REPLACE VIEW ena.v_tecnificacion_departamento AS
    SELECT 
        u.nombredd AS departamento,
        COUNT(DISTINCT f.id_productor) AS total_productores,
        SUM(CASE WHEN t.usa_fertilizantes THEN 1 ELSE 0 END) AS productores_con_fertilizantes,
        SUM(CASE WHEN t.realizo_analisis_suelo THEN 1 ELSE 0 END) AS productores_con_analisis_suelo,
        SUM(CASE WHEN t.aplica_conservacion_suelos THEN 1 ELSE 0 END) AS productores_con_conservacion,
        SUM(CASE WHEN t.riego_tecnificado THEN 1 ELSE 0 END) AS productores_riego_tecnificado
    FROM 
        ena.fact_produccion_agricola f
    JOIN 
        ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
    JOIN 
        ena.dim_tecnologia t ON f.id_tecnologia = t.id_tecnologia
    GROUP BY 
        u.nombredd
    """)
    
    # 4. Vista de servicios
    cursor.execute("""
    CREATE OR REPLACE VIEW ena.v_servicios_departamento AS
    SELECT 
        u.nombredd AS departamento,
        COUNT(DISTINCT s.id_productor) AS total_productores,
        SUM(CASE WHEN s.recibe_capacitacion THEN 1 ELSE 0 END) AS productores_capacitados,
        SUM(CASE WHEN s.es_organizado THEN 1 ELSE 0 END) AS productores_organizados,
        ROUND(100.0 * SUM(CASE WHEN s.recibe_capacitacion THEN 1 ELSE 0 END) / 
              NULLIF(COUNT(DISTINCT s.id_productor), 0), 2) AS porcentaje_capacitados,
        ROUND(100.0 * SUM(CASE WHEN s.es_organizado THEN 1 ELSE 0 END) / 
              NULLIF(COUNT(DISTINCT s.id_productor), 0), 2) AS porcentaje_organizados
    FROM 
        ena.fact_servicios s
    JOIN 
        ena.dim_ubicacion u ON s.id_ubicacion = u.id_ubicacion
    GROUP BY 
        u.nombredd
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("Vistas creadas exitosamente")
    return True

def main():
    try:
        logger.info("Iniciando carga de datos de la ENA 2021")
        
        # Verificar dependencias
        try:
            import chardet
        except ImportError:
            logger.info("Instalando dependencia chardet...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "chardet"])
            import chardet
        
        # Crear estructura de la base de datos
        ensure_schema_exists()
        ensure_tables_exist()
        clear_existing_data()
        
        # Cargar datos
        load_dimension_data()
        load_agricultural_data()
        load_livestock_data()
        load_services_data()
        create_views()
        
        logger.info("Proceso de carga completado exitosamente")
        logger.info("Puedes acceder a pgAdmin en http://localhost:5050 para ver los datos")
        logger.info("Credenciales: admin@admin.com / admin")
        
        return True
    except Exception as e:
        logger.error(f"Error en el proceso principal: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    main()