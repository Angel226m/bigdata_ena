-- Funciones para análisis 
-- Funciones útiles para análisis de datos ENA 2021

-- Función para obtener estadísticas agrícolas por departamento
CREATE OR REPLACE FUNCTION get_estadisticas_por_departamento()
RETURNS TABLE (
    departamento VARCHAR,
    total_productores BIGINT,
    superficie_sembrada_total DECIMAL,
    superficie_cosechada_total DECIMAL,
    produccion_total DECIMAL,
    rendimiento_promedio DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.nombredd,
        COUNT(DISTINCT f.id_productor) AS total_productores,
        SUM(f.superficie_sembrada) AS superficie_sembrada_total,
        SUM(f.superficie_cosechada) AS superficie_cosechada_total,
        SUM(f.produccion_total) AS produccion_total,
        CASE 
            WHEN SUM(f.superficie_cosechada) = 0 THEN 0
            ELSE SUM(f.produccion_total) / SUM(f.superficie_cosechada)
        END AS rendimiento_promedio
    FROM 
        fact_produccion_agricola f
    JOIN 
        dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
    GROUP BY 
        u.nombredd
    ORDER BY 
        superficie_sembrada_total DESC;
END;
$$ LANGUAGE plpgsql;

-- Función para obtener principales cultivos por región
CREATE OR REPLACE FUNCTION get_principales_cultivos_por_region(region_name VARCHAR)
RETURNS TABLE (
    cultivo VARCHAR,
    superficie_sembrada DECIMAL,
    produccion DECIMAL,
    rendimiento DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.nombre AS cultivo,
        SUM(f.superficie_sembrada) AS superficie_sembrada,
        SUM(f.produccion_total) AS produccion,
        CASE 
            WHEN SUM(f.superficie_cosechada) = 0 THEN 0
            ELSE SUM(f.produccion_total) / SUM(f.superficie_cosechada)
        END AS rendimiento
    FROM 
        fact_produccion_agricola f
    JOIN 
        dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
    JOIN 
        dim_cultivo c ON f.id_cultivo = c.id_cultivo
    WHERE 
        u.region = region_name
    GROUP BY 
        c.nombre
    ORDER BY 
        superficie_sembrada DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- Función para calcular indicadores del programa presupuestal
CREATE OR REPLACE FUNCTION calcular_indicadores_programa_presupuestal()
RETURNS TABLE (
    programa VARCHAR,
    indicador VARCHAR,
    valor DECIMAL,
    unidad VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    
    -- Indicadores para Programa 0042: Recursos Hídricos
    SELECT 
        '0042 - Recursos Hídricos' AS programa,
        'Superficie con riego tecnificado' AS indicador,
        (SUM(r.superficie_riego_tecnificado) / NULLIF(SUM(r.superficie_riego_tecnificado + r.superficie_riego_gravedad), 0)) * 100 AS valor,
        'Porcentaje' AS unidad
    FROM 
        fact_riego r
    
    UNION ALL
    
    SELECT 
        '0042 - Recursos Hídricos' AS programa,
        'Productores con prácticas adecuadas de riego' AS indicador,
        (COUNT(DISTINCT CASE WHEN r.capacitacion_riego = TRUE THEN r.id_productor END) * 100.0 / NULLIF(COUNT(DISTINCT r.id_productor), 0)) AS valor,
        'Porcentaje' AS unidad
    FROM 
        fact_riego r
    
    UNION ALL
    
    -- Indicadores para Programa 0089: Degradación de Suelos
    SELECT 
        '0089 - Degradación de Suelos' AS programa,
        'Productores con análisis de suelo' AS indicador,
        (COUNT(DISTINCT CASE WHEN t.analisis_suelo = TRUE THEN f.id_productor END) * 100.0 / NULLIF(COUNT(DISTINCT f.id_productor), 0)) AS valor,
        'Porcentaje' AS unidad
    FROM 
        fact_produccion_agricola f
    JOIN 
        dim_tecnologia t ON f.id_tecnologia = t.id_tecnologia
    
    UNION ALL
    
    SELECT 
        '0089 - Degradación de Suelos' AS programa,
        'Productores que usan fertilizantes adecuadamente' AS indicador,
        (COUNT(DISTINCT CASE WHEN t.usa_fertilizantes = TRUE THEN f.id_productor END) * 100.0 / NULLIF(COUNT(DISTINCT f.id_productor), 0)) AS valor,
        'Porcentaje' AS unidad
    FROM 
        fact_produccion_agricola f
    JOIN 
        dim_tecnologia t ON f.id_tecnologia = t.id_tecnologia
    
    UNION ALL
    
    -- Indicadores para Programa 0121: Articulación al Mercado
    SELECT 
        '0121 - Articulación al Mercado' AS programa,
        'Productores organizados empresarialmente' AS indicador,
        (COUNT(DISTINCT CASE WHEN s.es_organizado = TRUE THEN s.id_productor END) * 100.0 / NULLIF(COUNT(DISTINCT s.id_productor), 0)) AS valor,
        'Porcentaje' AS unidad
    FROM 
        fact_servicios_agrarios s
    
    UNION ALL
    
    SELECT 
        '0121 - Articulación al Mercado' AS programa,
        'Productores que comercializan su producción' AS indicador,
        (COUNT(DISTINCT CASE WHEN f.destino_venta > 50 THEN f.id_productor END) * 100.0 / NULLIF(COUNT(DISTINCT f.id_productor), 0)) AS valor,
        'Porcentaje' AS unidad
    FROM 
        fact_produccion_agricola f;
END;
$$ LANGUAGE plpgsql;