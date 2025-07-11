@echo off
echo ==============================================
echo    Iniciando servicios para Big Data ENA
echo ==============================================

REM Limpiar contenedores y volúmenes anteriores
echo [1/7] Deteniendo servicios anteriores y eliminando volúmenes...
docker-compose down -v

REM Construir imágenes actualizadas
echo [2/7] Construyendo imágenes Docker...
docker-compose build

REM Crear directorios si no existen
echo [3/7] Verificando directorios necesarios...
if not exist notebooks mkdir notebooks
if not exist init-scripts mkdir init-scripts

REM Ejecutar primero Zookeeper, Kafka y PostgreSQL
echo [4/7] Iniciando servicios base (Zookeeper, Kafka, PostgreSQL)...
docker-compose up -d zookeeper kafka postgres

REM Esperar a que los servicios estén disponibles
echo [5/7] Esperando a que los servicios estén disponibles (30 segundos)...
timeout /t 30 /nobreak > nul

REM Verificar codificación de archivos CSV
echo [6/7] Verificando codificación de archivos CSV...
docker-compose run --rm data-processor python check_encoding.py

REM Procesar datos
echo [7/7] Verificando archivos CSV y procesando datos...
docker-compose run --rm data-processor python check_files.py
docker-compose run --rm data-processor python process_data.py

REM Iniciar el resto de servicios
docker-compose up -d

echo ==============================================
echo    Servicios iniciados correctamente
echo ==============================================
echo.
echo Accede a Jupyter Notebook en: http://localhost:8888
echo Para detener los servicios, ejecuta stop-services.bat
echo.