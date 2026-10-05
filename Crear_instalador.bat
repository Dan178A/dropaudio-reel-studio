@echo off
rem Crea el instalador local (Releases\ReelStudio-win-Setup.exe) con Velopack, sin publicar nada.
cd /d "%~dp0"
set SIN_PAUSA=1
call Crear_exe.bat || goto :err
for /f "delims=" %%v in ('python -c "from version import __version__; print(__version__)"') do set VERSION=%%v
if "%VERSION%"=="" goto :err
set "PATH=%PATH%;%USERPROFILE%\.dotnet\tools"
where vpk >nul 2>nul || dotnet tool install -g vpk || goto :err
vpk pack --packId ReelStudio --packVersion %VERSION% --packDir dist\ReelStudio --mainExe ReelStudio.exe --packTitle "Reel Studio" --icon icon.ico --outputDir Releases || goto :err
echo.
echo Listo: instalador en Releases\ (version %VERSION%). No se publico nada.
pause
exit /b 0
:err
echo Algo fallo. Copia el error y pasaselo a Claude.
pause
exit /b 1
