# Script de vistas para reportes 
-- Vista para reporte de producción agrícola por departamento
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
    u.nombredd, c.p204_nom, c.p204_tipo;

-- Vista para reporte de producción pecuaria por departamento
CREATE OR REPLACE VIEW ena.v_produccion_pecuaria_departamento AS
SELECT 
    u.nombredd AS departamento,
    a.nombre AS animal,
    a.tipo AS tipo_animal,
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
    u.nombredd, a.nombre, a.tipo;

-- Vista para reporte de tecnificación por departamento
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
    u.nombredd;

-- Vista para reporte de servicios por departamento
CREATE OR REPLACE VIEW ena.v_servicios_departamento AS
SELECT 
    u.nombredd AS departamento,
    COUNT(DISTINCT s.id_productor) AS total_productores,
    SUM(CASE WHEN s.recibe_capacitacion THEN 1 ELSE 0 END) AS productores_capacitados,
    SUM(CASE WHEN s.es_organizado THEN 1 ELSE 0 END) AS productores_organizados,
    ROUND(100.0 * SUM(CASE WHEN s.recibe_capacitacion THEN 1 ELSE 0 END) / COUNT(DISTINCT s.id_productor), 2) AS porcentaje_capacitados,
    ROUND(100.0 * SUM(CASE WHEN s.es_organizado THEN 1 ELSE 0 END) / COUNT(DISTINCT s.id_productor), 2) AS porcentaje_organizados
FROM 
    ena.fact_servicios s
JOIN 
    ena.dim_ubicacion u ON s.id_ubicacion = u.id_ubicacion
GROUP BY 
    u.nombredd;