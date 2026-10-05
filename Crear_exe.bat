@echo off
rem Empaqueta Reel Studio como app de Windows: dist\ReelStudio\ReelStudio.exe
rem Usa ReelStudio.spec (unica fuente de verdad del empaquetado; no lo regenera).
cd /d "%~dp0"
pip install -r requirements.txt pyinstaller || goto :err
pyinstaller --noconfirm ReelStudio.spec || goto :err
echo.
echo Listo: dist\ReelStudio\ReelStudio.exe  (puedes anclarlo a la barra de tareas)
if not "%SIN_PAUSA%"=="1" pause
exit /b 0
:err
echo Algo fallo. Copia el error y pasaselo a Claude.
if not "%SIN_PAUSA%"=="1" pause
exit /b 1
