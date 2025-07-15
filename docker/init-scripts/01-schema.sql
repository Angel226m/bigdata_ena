-- Crear esquema para organizar los objetos
CREATE SCHEMA IF NOT EXISTS ena;

-- Crear tablas dimensionales mejoradas
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
);

CREATE INDEX IF NOT EXISTS idx_dim_ubicacion_ccdd ON ena.dim_ubicacion(ccdd);
CREATE INDEX IF NOT EXISTS idx_dim_ubicacion_region ON ena.dim_ubicacion(region);

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
    lengua_materna VARCHAR(50),
    pertenece_organizacion BOOLEAN,
    tipo_organizacion VARCHAR(50),
    experiencia_agricultura INTEGER,
    es_pequeño_mediano BOOLEAN,
    UNIQUE(codigo, conglomerado, nselua, ua)
);

CREATE INDEX IF NOT EXISTS idx_dim_productor_codigo ON ena.dim_productor(codigo);

CREATE TABLE IF NOT EXISTS ena.dim_cultivo (
    id_cultivo SERIAL PRIMARY KEY,
    codigo VARCHAR(10),
    nombre VARCHAR(200),
    tipo VARCHAR(100),
    categoria VARCHAR(50),
    ciclo_productivo VARCHAR(50),
    uso_semilla_certificada BOOLEAN,
    UNIQUE(codigo)
);

CREATE INDEX IF NOT EXISTS idx_dim_cultivo_nombre ON ena.dim_cultivo(nombre);

CREATE TABLE IF NOT EXISTS ena.dim_animal (
    id_animal SERIAL PRIMARY KEY,
    codigo VARCHAR(10),
    nombre VARCHAR(100),
    tipo VARCHAR(50),
    raza BOOLEAN,
    proposito VARCHAR(50),
    UNIQUE(codigo)
);

CREATE INDEX IF NOT EXISTS idx_dim_animal_nombre ON ena.dim_animal(nombre);

CREATE TABLE IF NOT EXISTS ena.dim_tiempo (
    id_tiempo SERIAL PRIMARY KEY,
    anio INTEGER,
    mes INTEGER,
    trimestre INTEGER,
    campaña VARCHAR(50),
    UNIQUE(anio, mes, trimestre)
);

CREATE TABLE IF NOT EXISTS ena.dim_tecnologia (
    id_tecnologia SERIAL PRIMARY KEY,
    realizo_analisis_suelo BOOLEAN,
    recibio_asistencia_analisis BOOLEAN,
    aplica_conservacion_suelos BOOLEAN,
    usa_curvas_nivel BOOLEAN,
    usa_terrazas BOOLEAN,
    usa_zanjas_infiltracion BOOLEAN,
    usa_barreras_vivas BOOLEAN,
    aplica_rotacion_cultivos BOOLEAN,
    usa_fertilizantes BOOLEAN,
    usa_abonos_organicos BOOLEAN,
    realiza_practicas_fertilizacion BOOLEAN,
    usa_plaguicidas BOOLEAN,
    aplica_manejo_plagas BOOLEAN,
    cuenta_sistema_riego BOOLEAN,
    tipo_sistema_riego VARCHAR(50),
    riego_tecnificado BOOLEAN,
    capacitado_uso_agua BOOLEAN
);

-- Crear tablas de hechos para datos agrícolas
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
    costo_mano_obra DECIMAL(12,2),
    costo_total DECIMAL(12,2),
    destino_venta DECIMAL(12,2),
    destino_autoconsumo DECIMAL(12,2),
    destino_autoinsumo DECIMAL(12,2),
    destino_almacenado DECIMAL(12,2),
    orientacion_siembras BOOLEAN,
    adecuada_orientacion_siembras BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_fact_agricola_ubicacion ON ena.fact_produccion_agricola(id_ubicacion);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_productor ON ena.fact_produccion_agricola(id_productor);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_cultivo ON ena.fact_produccion_agricola(id_cultivo);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_tiempo ON ena.fact_produccion_agricola(id_tiempo);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_tecnologia ON ena.fact_produccion_agricola(id_tecnologia);

-- Crear tabla de hechos para datos pecuarios
CREATE TABLE IF NOT EXISTS ena.fact_produccion_pecuaria (
    id_produccion SERIAL PRIMARY KEY,
    id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
    id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
    id_animal INTEGER REFERENCES ena.dim_animal(id_animal),
    id_tiempo INTEGER REFERENCES ena.dim_tiempo(id_tiempo),
    factor DECIMAL(12,6),
    numero_animales INTEGER,
    numero_crias INTEGER,
    produccion_leche DECIMAL(12,2),
    produccion_huevos DECIMAL(12,2),
    produccion_carne DECIMAL(12,2),
    produccion_lana DECIMAL(12,2),
    produccion_fibra DECIMAL(12,2),
    precio_venta DECIMAL(12,2),
    costo_alimentacion DECIMAL(12,2),
    costo_sanitario DECIMAL(12,2),
    costo_mano_obra DECIMAL(12,2),
    costo_total DECIMAL(12,2),
    uso_reproductores_calidad BOOLEAN,
    capacitado_manejo_pastos BOOLEAN,
    recibio_asistencia_pastos BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_ubicacion ON ena.fact_produccion_pecuaria(id_ubicacion);
CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_productor ON ena.fact_produccion_pecuaria(id_productor);
CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_animal ON ena.fact_produccion_pecuaria(id_animal);
CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_tiempo ON ena.fact_produccion_pecuaria(id_tiempo);

-- Crear tabla para servicios agropecuarios
CREATE TABLE IF NOT EXISTS ena.fact_servicios (
    id_servicio SERIAL PRIMARY KEY,
    id_productor INTEGER REFERENCES ena.dim_productor(id_productor),
    id_ubicacion INTEGER REFERENCES ena.dim_ubicacion(id_ubicacion),
    id_tiempo INTEGER REFERENCES ena.dim_tiempo(id_tiempo),
    recibe_capacitacion BOOLEAN,
    tema_capacitacion VARCHAR(100),
    institucion_capacitadora VARCHAR(100),
    recibe_asistencia_tecnica BOOLEAN,
    tema_asistencia VARCHAR(100),
    institucion_asistencia VARCHAR(100),
    usa_servicio_informacion BOOLEAN,
    tipo_informacion VARCHAR(100),
    es_organizado BOOLEAN,
    tipo_organizacion VARCHAR(100),
    gestion_empresarial BOOLEAN,
    acceso_credito BOOLEAN,
    entidad_credito VARCHAR(100),
    monto_credito DECIMAL(12,2),
    tiene_seguro BOOLEAN,
    tipo_seguro VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_servicios_productor ON ena.fact_servicios(id_productor);
CREATE INDEX IF NOT EXISTS idx_servicios_ubicacion ON ena.fact_servicios(id_ubicacion);
CREATE INDEX IF NOT EXISTS idx_servicios_tiempo ON ena.fact_servicios(id_tiempo);