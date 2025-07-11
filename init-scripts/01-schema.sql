-- Esquema para base de datos ENA 
-- Creación de esquema para la Encuesta Nacional Agropecuaria (ENA) 2021
-- Este script crea todas las tablas dimensionales y de hechos necesarias

-- Tablas de dimensiones
CREATE TABLE dim_ubicacion (
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

CREATE TABLE dim_productor (
    id_productor SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE,
    tipo_productor VARCHAR(100),        -- P102_1
    condicion_juridica VARCHAR(100),    -- P102_2
    nivel_educativo VARCHAR(100),       -- P105_N
    sexo VARCHAR(10),                   -- De Cap1100
    edad INTEGER,                       -- De Cap1100
    experiencia_agropecuaria INTEGER    -- De Cap1100
);

CREATE TABLE dim_cultivo (
    id_cultivo SERIAL PRIMARY KEY,
    codigo VARCHAR(10) UNIQUE,          -- P204_COD
    nombre VARCHAR(100),                -- P204_NOM
    tipo VARCHAR(50)                    -- P204_TIPO
);

CREATE TABLE dim_tiempo (
    id_tiempo SERIAL PRIMARY KEY,
    anio INTEGER,
    trimestre INTEGER,
    mes INTEGER,
    UNIQUE(anio, trimestre, mes)
);

CREATE TABLE dim_tecnologia (
    id_tecnologia SERIAL PRIMARY KEY,
    usa_fertilizantes BOOLEAN,
    analisis_suelo BOOLEAN,
    riego_tecnificado BOOLEAN,
    conservacion_suelos BOOLEAN,
    asistencia_tecnica BOOLEAN
);

-- Tablas de hechos principales

-- 1. Tabla de hechos para producción agrícola (Cap200)
CREATE TABLE fact_produccion_agricola (
    id_produccion SERIAL PRIMARY KEY,
    id_ubicacion INTEGER REFERENCES dim_ubicacion(id_ubicacion),
    id_productor INTEGER REFERENCES dim_productor(id_productor),
    id_cultivo INTEGER REFERENCES dim_cultivo(id_cultivo),
    id_tiempo INTEGER REFERENCES dim_tiempo(id_tiempo),
    id_tecnologia INTEGER REFERENCES dim_tecnologia(id_tecnologia),
    conglomerado VARCHAR(20),
    nselua VARCHAR(20),
    ua VARCHAR(20),
    resfin VARCHAR(10),
    factor DECIMAL(10,4),
    superficie_sembrada DECIMAL(10,2),      -- P218A
    superficie_cosechada DECIMAL(10,2),     -- P218B
    numero_cortes INTEGER,                  -- P218C_NRO
    produccion_total DECIMAL(15,2),         -- P218C_PROD calculada
    rendimiento DECIMAL(10,2),              -- Calculado como produccion/superficie
    costo_semilla DECIMAL(10,2),            -- De Cap200e
    costo_fertilizante DECIMAL(10,2),       -- De Cap200e
    costo_plaguicida DECIMAL(10,2),         -- De Cap200e
    costo_mano_obra DECIMAL(10,2),          -- De Cap200e
    destino_venta DECIMAL(5,2),             -- Porcentaje a venta de Cap200d
    destino_autoconsumo DECIMAL(5,2)        -- Porcentaje a autoconsumo de Cap200d
);

-- 2. Tabla de hechos para producción pecuaria (Cap400)
CREATE TABLE fact_produccion_pecuaria (
    id_produccion_pecuaria SERIAL PRIMARY KEY,
    id_ubicacion INTEGER REFERENCES dim_ubicacion(id_ubicacion),
    id_productor INTEGER REFERENCES dim_productor(id_productor),
    id_tiempo INTEGER REFERENCES dim_tiempo(id_tiempo),
    conglomerado VARCHAR(20),
    nselua VARCHAR(20),
    ua VARCHAR(20),
    resfin VARCHAR(10),
    factor DECIMAL(10,4),
    tipo_animal VARCHAR(50),                -- De Cap400a_1
    cantidad_animales INTEGER,              -- De Cap400a_1
    produccion_leche DECIMAL(10,2),         -- De Cap400a_2
    produccion_huevos DECIMAL(10,2),        -- De Cap400a_2
    produccion_lana DECIMAL(10,2),          -- De Cap400a_2
    usa_reproductores_calidad BOOLEAN,      -- De Cap400c
    vacunacion BOOLEAN,                     -- De Cap400c
    alimento_balanceado BOOLEAN             -- De Cap400c
);

-- 3. Tabla de hechos para servicios agrarios (Cap700, Cap800, Cap1000)
CREATE TABLE fact_servicios_agrarios (
    id_servicios SERIAL PRIMARY KEY,
    id_ubicacion INTEGER REFERENCES dim_ubicacion(id_ubicacion),
    id_productor INTEGER REFERENCES dim_productor(id_productor),
    id_tiempo INTEGER REFERENCES dim_tiempo(id_tiempo),
    conglomerado VARCHAR(20),
    nselua VARCHAR(20),
    ua VARCHAR(20),
    resfin VARCHAR(10),
    factor DECIMAL(10,4),
    recibe_capacitacion BOOLEAN,            -- De Cap700
    tipo_capacitacion VARCHAR(100),         -- De Cap700
    institucion_capacitadora VARCHAR(100),  -- De Cap700
    es_organizado BOOLEAN,                  -- De Cap800
    tipo_organizacion VARCHAR(100),         -- De Cap800
    beneficios_organizacion VARCHAR(200),   -- De Cap800
    acceso_informacion BOOLEAN,             -- De Cap1000
    tipo_informacion VARCHAR(100)           -- De Cap1000
);

-- 4. Tabla de hechos para riego y agua (Cap500)
CREATE TABLE fact_riego (
    id_riego SERIAL PRIMARY KEY,
    id_ubicacion INTEGER REFERENCES dim_ubicacion(id_ubicacion),
    id_productor INTEGER REFERENCES dim_productor(id_productor),
    id_tiempo INTEGER REFERENCES dim_tiempo(id_tiempo),
    conglomerado VARCHAR(20),
    nselua VARCHAR(20),
    ua VARCHAR(20),
    resfin VARCHAR(10),
    factor DECIMAL(10,4),
    tipo_riego VARCHAR(50),                 -- De Cap500ab
    fuente_agua VARCHAR(50),                -- De Cap500ab
    superficie_riego_tecnificado DECIMAL(10,2), -- De Cap500ab
    superficie_riego_gravedad DECIMAL(10,2),    -- De Cap500ab
    capacitacion_riego BOOLEAN              -- De Cap500ab
);

-- Crear índices para optimizar consultas
CREATE INDEX idx_fact_agri_ubicacion ON fact_produccion_agricola(id_ubicacion);
CREATE INDEX idx_fact_agri_productor ON fact_produccion_agricola(id_productor);
CREATE INDEX idx_fact_agri_cultivo ON fact_produccion_agricola(id_cultivo);
CREATE INDEX idx_fact_agri_tiempo ON fact_produccion_agricola(id_tiempo);

CREATE INDEX idx_fact_pec_ubicacion ON fact_produccion_pecuaria(id_ubicacion);
CREATE INDEX idx_fact_pec_productor ON fact_produccion_pecuaria(id_productor);
CREATE INDEX idx_fact_pec_tiempo ON fact_produccion_pecuaria(id_tiempo);

CREATE INDEX idx_fact_serv_ubicacion ON fact_servicios_agrarios(id_ubicacion);
CREATE INDEX idx_fact_serv_productor ON fact_servicios_agrarios(id_productor);
CREATE INDEX idx_fact_serv_tiempo ON fact_servicios_agrarios(id_tiempo);

CREATE INDEX idx_fact_riego_ubicacion ON fact_riego(id_ubicacion);
CREATE INDEX idx_fact_riego_productor ON fact_riego(id_productor);
CREATE INDEX idx_fact_riego_tiempo ON fact_riego(id_tiempo);