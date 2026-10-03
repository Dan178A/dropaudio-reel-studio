@echo off
rem Empaqueta Reel Studio como app de Windows: dist\ReelStudio\ReelStudio.exe
cd /d "%~dp0"
pip install pyinstaller pywebview pymediainfo imageio || goto :err
pyinstaller --noconfirm --windowed --name ReelStudio --icon icon.ico ^
  --add-data "studio.html;." --paths "..\pyCapCut" ^
  --add-data "..\pyCapCut\pycapcut\assets;pycapcut\assets" ^
  --hidden-import gen_music --hidden-import pillow_heif --hidden-import pycapcut --hidden-import imageio ^
  --collect-all pymediainfo ^
  --collect-all faster_whisper --collect-all ctranslate2 --collect-submodules pycapcut ^
  ReelStudio.pyw || goto :err
echo.
echo Listo: dist\ReelStudio\ReelStudio.exe  (puedes anclarlo a la barra de tareas)
pause
exit /b 0
:err
echo Algo fallo. Copia el error y pasaselo a Claude.
pause
