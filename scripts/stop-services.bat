@echo off
echo ==============================================
echo    Deteniendo servicios Big Data ENA
echo ==============================================

echo [1/1] Deteniendo todos los servicios...
docker-compose down

echo ==============================================
echo    Servicios detenidos correctamente
echo ==============================================