# Script de esquema de base de datos 
-- Crear esquema para organizar los objetos
CREATE SCHEMA IF NOT EXISTS ena;

-- Crear tablas dimensionales
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
);

CREATE TABLE IF NOT EXISTS ena.dim_productor (
    id_productor SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE,
    p102_1 VARCHAR(200),  -- Tipo de productor
    p102_2 VARCHAR(200),  -- Condición jurídica
    p105_n VARCHAR(200),  -- Nivel educativo
    sexo VARCHAR(20),     -- Sexo del productor
    edad INTEGER,         -- Edad del productor
    experiencia INTEGER   -- Años de experiencia
);

CREATE TABLE IF NOT EXISTS ena.dim_cultivo (
    id_cultivo SERIAL PRIMARY KEY,
    p204_cod VARCHAR(10),
    p204_nom VARCHAR(200),
    p204_tipo VARCHAR(100),
    UNIQUE(p204_cod)
);

CREATE TABLE IF NOT EXISTS ena.dim_animal (
    id_animal SERIAL PRIMARY KEY,
    codigo VARCHAR(10),
    nombre VARCHAR(100),
    tipo VARCHAR(50),
    UNIQUE(codigo)
);

CREATE TABLE IF NOT EXISTS ena.dim_tiempo (
    id_tiempo SERIAL PRIMARY KEY,
    anio INTEGER,
    trimestre INTEGER,
    mes INTEGER,
    UNIQUE(anio, trimestre, mes)
);

CREATE TABLE IF NOT EXISTS ena.dim_tecnologia (
    id_tecnologia SERIAL PRIMARY KEY,
    usa_fertilizantes BOOLEAN,
    tipo_fertilizante VARCHAR(100),
    tiene_analisis_suelo BOOLEAN,
    practica_conservacion BOOLEAN,
    tipo_riego VARCHAR(50),
    fuente_agua VARCHAR(50)
);

-- Crear tabla de hechos para datos agrícolas
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
);

-- Crear tabla de hechos para datos pecuarios
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
);

-- Crear tabla para servicios agropecuarios
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
);

-- Crear índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_fact_agricola_ubicacion ON ena.fact_produccion_agricola(id_ubicacion);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_productor ON ena.fact_produccion_agricola(id_productor);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_cultivo ON ena.fact_produccion_agricola(id_cultivo);
CREATE INDEX IF NOT EXISTS idx_fact_agricola_tiempo ON ena.fact_produccion_agricola(id_tiempo);

CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_ubicacion ON ena.fact_produccion_pecuaria(id_ubicacion);
CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_productor ON ena.fact_produccion_pecuaria(id_productor);
CREATE INDEX IF NOT EXISTS idx_fact_pecuaria_animal ON ena.fact_produccion_pecuaria(id_animal);

CREATE INDEX IF NOT EXISTS idx_servicios_productor ON ena.fact_servicios(id_productor);
CREATE INDEX IF NOT EXISTS idx_servicios_ubicacion ON ena.fact_servicios(id_ubicacion);