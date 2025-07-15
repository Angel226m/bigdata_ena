-- 1. Vista para producción agrícola por departamento y cultivo
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
    END AS rendimiento_ha,
    AVG(f.precio_chacra) AS precio_chacra_promedio,
    SUM(f.destino_venta) AS cantidad_venta,
    SUM(f.destino_autoconsumo) AS cantidad_autoconsumo
FROM 
    ena.fact_produccion_agricola f
JOIN 
    ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
JOIN 
    ena.dim_cultivo c ON f.id_cultivo = c.id_cultivo
GROUP BY 
    u.nombredd, c.nombre, c.tipo;

-- 2. Vista para producción pecuaria por departamento y animal
CREATE OR REPLACE VIEW ena.v_produccion_pecuaria_departamento AS
SELECT 
    u.nombredd AS departamento,
    a.nombre AS animal,
    SUM(f.numero_animales) AS total_animales,
    SUM(f.produccion_leche) AS produccion_leche,
    SUM(f.produccion_huevos) AS produccion_huevos,
    SUM(f.produccion_carne) AS produccion_carne,
    COUNT(DISTINCT f.id_productor) AS total_productores,
    SUM(CASE WHEN f.uso_reproductores_calidad THEN 1 ELSE 0 END) AS productores_usan_reproductores
FROM 
    ena.fact_produccion_pecuaria f
JOIN 
    ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
JOIN 
    ena.dim_animal a ON f.id_animal = a.id_animal
GROUP BY 
    u.nombredd, a.nombre;

-- 3. Vista para indicadores del PP0089: Reducción de la degradación de los suelos agrarios
CREATE OR REPLACE VIEW ena.v_pp0089_degradacion_suelos AS
SELECT 
    u.nombredd AS departamento,
    u.region AS region_natural,
    COUNT(DISTINCT p.id_productor) AS total_productores,
    SUM(CASE WHEN f.orientacion_siembras THEN 1 ELSE 0 END) AS productores_con_orientacion_siembras,
    SUM(CASE WHEN f.adecuada_orientacion_siembras THEN 1 ELSE 0 END) AS productores_adecuada_orientacion,
    SUM(CASE WHEN t.realizo_analisis_suelo THEN 1 ELSE 0 END) AS productores_analisis_suelo,
    SUM(CASE WHEN t.recibio_asistencia_analisis THEN 1 ELSE 0 END) AS productores_asistencia_analisis,
    SUM(CASE WHEN t.aplica_conservacion_suelos THEN 1 ELSE 0 END) AS productores_conservacion_suelos,
    SUM(CASE WHEN t.usa_fertilizantes THEN 1 ELSE 0 END) AS productores_usan_fertilizantes,
    SUM(CASE WHEN t.realiza_practicas_fertilizacion THEN 1 ELSE 0 END) AS productores_buenas_practicas_fertilizacion,
    SUM(CASE WHEN t.usa_plaguicidas THEN 1 ELSE 0 END) AS productores_usan_plaguicidas,
    SUM(CASE WHEN t.aplica_manejo_plagas THEN 1 ELSE 0 END) AS productores_buenas_practicas_plaguicidas
FROM 
    ena.fact_produccion_agricola f
JOIN 
    ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
JOIN 
    ena.dim_productor p ON f.id_productor = p.id_productor
JOIN 
    ena.dim_tecnologia t ON f.id_tecnologia = t.id_tecnologia
GROUP BY 
    u.nombredd, u.region;

-- 4. Vista para indicadores del PP0042: Aprovechamiento de los recursos hídricos
CREATE OR REPLACE VIEW ena.v_pp0042_recursos_hidricos AS
SELECT 
    u.nombredd AS departamento,
    u.region AS region_natural,
    COUNT(DISTINCT p.id_productor) AS total_productores,
    SUM(CASE WHEN t.cuenta_sistema_riego THEN 1 ELSE 0 END) AS productores_con_riego,
    SUM(CASE WHEN t.tipo_sistema_riego IN ('2', '3', 'Aspersión', 'Goteo') THEN 1 ELSE 0 END) AS productores_riego_tecnificado,
    SUM(CASE WHEN t.capacitado_uso_agua THEN 1 ELSE 0 END) AS productores_capacitados_uso_agua,
    SUM(f.superficie_sembrada) AS superficie_sembrada_total,
    SUM(CASE WHEN t.riego_tecnificado THEN f.superficie_sembrada ELSE 0 END) AS superficie_riego_tecnificado
FROM 
    ena.fact_produccion_agricola f
JOIN 
    ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
JOIN 
    ena.dim_productor p ON f.id_productor = p.id_productor
JOIN 
    ena.dim_tecnologia t ON f.id_tecnologia = t.id_tecnologia
GROUP BY 
    u.nombredd, u.region;

-- 5. Vista para indicadores del PP0121: Mejora de articulación de pequeños productores
CREATE OR REPLACE VIEW ena.v_pp0121_articulacion_mercado AS
SELECT 
    u.nombredd AS departamento,
    u.region AS region_natural,
    COUNT(DISTINCT p.id_productor) AS total_productores,
    SUM(CASE WHEN s.es_organizado THEN 1 ELSE 0 END) AS productores_organizados,
    SUM(CASE WHEN s.gestion_empresarial THEN 1 ELSE 0 END) AS productores_gestion_empresarial,
    SUM(CASE WHEN c.uso_semilla_certificada THEN 1 ELSE 0 END) AS productores_semilla_certificada,
    SUM(CASE WHEN a.raza THEN 1 ELSE 0 END) AS productores_reproductores_calidad,
    SUM(CASE WHEN s.usa_servicio_informacion THEN 1 ELSE 0 END) AS productores_usan_informacion,
    COUNT(CASE WHEN f.destino_venta > 0 THEN p.id_productor END) AS productores_venden,
    SUM(f.produccion_total) AS produccion_total,
    SUM(f.destino_venta) AS cantidad_venta,
    SUM(CASE WHEN f.destino_venta > 0.5 * f.produccion_total THEN 1 ELSE 0 END) AS productores_venden_mayoria
FROM 
    ena.dim_productor p
JOIN 
    ena.dim_ubicacion u ON u.id_ubicacion = (SELECT id_ubicacion FROM ena.fact_produccion_agricola WHERE id_productor = p.id_productor LIMIT 1)
LEFT JOIN 
    ena.fact_servicios s ON p.id_productor = s.id_productor
LEFT JOIN 
    ena.fact_produccion_agricola f ON p.id_productor = f.id_productor
LEFT JOIN 
    ena.dim_cultivo c ON f.id_cultivo = c.id_cultivo
LEFT JOIN 
    ena.fact_produccion_pecuaria fp ON p.id_productor = fp.id_productor
LEFT JOIN 
    ena.dim_animal a ON fp.id_animal = a.id_animal
GROUP BY 
    u.nombredd, u.region;

-- 6. Vista para resultados de capacitación y asistencia técnica
CREATE OR REPLACE VIEW ena.v_servicios_extension_agraria AS
SELECT 
    u.nombredd AS departamento,
    u.region AS region_natural,
    COUNT(DISTINCT s.id_productor) AS total_productores,
    SUM(CASE WHEN s.recibe_capacitacion THEN 1 ELSE 0 END) AS productores_capacitados,
    SUM(CASE WHEN s.recibe_asistencia_tecnica THEN 1 ELSE 0 END) AS productores_asistencia_tecnica,
    SUM(CASE WHEN s.usa_servicio_informacion THEN 1 ELSE 0 END) AS productores_servicios_informacion,
    COUNT(DISTINCT s.institucion_capacitadora) AS entidades_capacitadoras,
    COUNT(DISTINCT s.institucion_asistencia) AS entidades_asistencia,
    SUM(CASE WHEN s.acceso_credito THEN 1 ELSE 0 END) AS productores_credito,
    SUM(CASE WHEN s.tiene_seguro THEN 1 ELSE 0 END) AS productores_seguro
FROM 
    ena.fact_servicios s
JOIN 
    ena.dim_ubicacion u ON s.id_ubicacion = u.id_ubicacion
GROUP BY 
    u.nombredd, u.region;

-- 7. Vista para indicadores de rendimiento de principales cultivos
CREATE OR REPLACE VIEW ena.v_rendimiento_cultivos AS
SELECT 
    c.nombre AS cultivo,
    u.nombredd AS departamento,
    SUM(f.superficie_sembrada) AS superficie_sembrada,
    SUM(f.superficie_cosechada) AS superficie_cosechada,
    SUM(f.produccion_total) AS produccion_total,
    CASE 
        WHEN SUM(f.superficie_cosechada) > 0 THEN SUM(f.produccion_total) / SUM(f.superficie_cosechada)
        ELSE 0
    END AS rendimiento_ha,
    AVG(f.precio_chacra) AS precio_chacra_promedio,
    COUNT(DISTINCT f.id_productor) AS total_productores,
    AVG(f.costo_total) AS costo_produccion_promedio
FROM 
    ena.fact_produccion_agricola f
JOIN 
    ena.dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
JOIN 
    ena.dim_cultivo c ON f.id_cultivo = c.id_cultivo
GROUP BY 
    c.nombre, u.nombredd
ORDER BY 
    c.nombre, u.nombredd;