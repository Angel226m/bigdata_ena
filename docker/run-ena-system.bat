@echo off
echo ====================================================
echo    Sistema Big Data ENA 2021 - Inicializacion
echo ====================================================
echo.

REM Verificar si Docker Desktop está ejecutándose
echo Verificando Docker...
docker info > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker no esta ejecutandose. Por favor inicie Docker Desktop.
    pause
    exit /b 1
)

REM Verificar existencia de carpetas de datos
if not exist "data" (
    echo Creando carpeta de datos...
    mkdir data
)

echo.
echo Verificando archivos CSV...
if not exist "data\*.csv" (
    echo ADVERTENCIA: No se encuentran archivos CSV en la carpeta data.
    echo Por favor copie los archivos CSV de la ENA 2021 a la carpeta data
    choice /C YN /M "¿Desea continuar de todos modos?"
    if %ERRORLEVEL% NEQ 1 exit /b 1
)

echo.
echo Iniciando contenedores Docker...
docker-compose down
docker-compose up -d

echo.
echo Mostrando logs del cargador de datos...
docker logs -f data-loader-ena

echo.
echo Sistema inicializado. Puedes acceder a pgAdmin en http://localhost:5050
echo Credenciales pgAdmin:
echo   Email: admin@admin.com
echo   Password: admin
echo.
echo Para conectar a la base de datos desde pgAdmin:
echo   Host: postgres
echo   Puerto: 5432
echo   Base de datos: ena_database
echo   Usuario: postgres
echo   Contraseña: postgres
echo.

pause