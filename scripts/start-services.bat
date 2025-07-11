@echo off
echo Iniciando servicios...

REM Limpiar contenedores y volúmenes anteriores
docker-compose down -v

REM Construir imágenes actualizadas
docker-compose build

REM Ejecutar primero el verificador de archivos
docker-compose run --rm data-processor python check_files.py

REM Si quieres continuar a pesar de posibles problemas con archivos
echo Presiona cualquier tecla para continuar o Ctrl+C para cancelar...
pause > nul

REM Iniciar todos los servicios
docker-compose up -d

echo Servicios iniciados correctamente.
echo Accede a Jupyter Notebook en: http://localhost:8888