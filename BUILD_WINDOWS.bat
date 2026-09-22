@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Premium Clip Cutter - Windows Builder
cd /d "%~dp0"

echo ==============================================================
echo          PREMIUM CLIP CUTTER - ONE CLICK WINDOWS BUILD
 echo ==============================================================
echo.
echo This builder creates:
echo   - Standalone PremiumClipCutter.exe
echo   - Bundled FFmpeg (no separate FFmpeg install needed)
echo   - Windows installer Setup.exe
 echo   - Desktop + Start Menu shortcuts
 echo   - Uninstaller
 echo.
echo Build requires internet and may take 10-30+ minutes.
echo The final EXE may be large because Whisper/Torch are included.
echo.
pause

if not exist build_tools mkdir build_tools
if not exist vendor mkdir vendor
if not exist vendor\ffmpeg mkdir vendor\ffmpeg

where py >nul 2>&1
if errorlevel 1 (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python was not found. Trying winget...
    where winget >nul 2>&1
    if errorlevel 1 (
      echo ERROR: Python is not installed and winget is unavailable.
      echo Install Python 3.11+ from python.org, then run this file again.
      pause
      exit /b 1
    )
    winget install Python.Python.3.11 --exact --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :fail
  )
  set PYTHON=python
) else (
  set PYTHON=py -3
)

%PYTHON% --version
if errorlevel 1 goto :fail

if not exist app.ico (
  echo [1/6] Creating application icon...
  %PYTHON% -m pip install --disable-pip-version-check pillow
  if errorlevel 1 goto :fail
  %PYTHON% make_icon.py
  if errorlevel 1 goto :fail
) else echo [1/6] Icon already exists.

if not exist vendor\ffmpeg\bin\ffmpeg.exe (
  echo [2/6] Downloading FFmpeg...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile 'build_tools\ffmpeg.zip'"
  if errorlevel 1 goto :fail
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force 'build_tools\ffmpeg.zip' 'build_tools\ffmpeg_extract'"
  if errorlevel 1 goto :fail
  for /d %%D in (build_tools\ffmpeg_extract\ffmpeg-*) do xcopy /E /I /Y "%%D\bin" "vendor\ffmpeg\bin" >nul
  if not exist vendor\ffmpeg\bin\ffmpeg.exe (
    echo ERROR: FFmpeg download/extraction failed.
    goto :fail
  )
) else echo [2/6] FFmpeg already present.

 echo [3/6] Installing Python packages...
%PYTHON% -m pip install --upgrade pip
if errorlevel 1 goto :fail
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 goto :fail
%PYTHON% -m pip install pyinstaller
if errorlevel 1 goto :fail

 echo [4/6] Building PremiumClipCutter.exe...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name PremiumClipCutter --icon app.ico --add-data "app.ico;." --add-binary "vendor\ffmpeg\bin\ffmpeg.exe;ffmpeg" --add-binary "vendor\ffmpeg\bin\ffprobe.exe;ffmpeg" --collect-all whisper --collect-all yt_dlp --collect-all tiktoken --collect-all numba --collect-all llvmlite --collect-all torch gui_app.py
if errorlevel 1 goto :fail
if not exist dist\PremiumClipCutter.exe goto :fail

 echo [5/6] Installing Inno Setup builder...
where iscc >nul 2>&1
if errorlevel 1 (
  where winget >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Inno Setup compiler not found and winget unavailable.
    echo Install Inno Setup, then run this builder again.
    goto :fail
  )
  winget install JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 goto :fail
)

set ISCC=
for %%I in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe") do if exist %%~I set ISCC=%%~I
if "%ISCC%"=="" set ISCC=iscc

 echo [6/6] Creating Windows installer...
%ISCC% installer.iss
if errorlevel 1 goto :fail
if not exist Output\PremiumClipCutter_Setup.exe goto :fail

echo.
echo ==============================================================
echo BUILD SUCCESSFUL!
echo.
echo Standalone EXE:
echo   %CD%\dist\PremiumClipCutter.exe
echo.
echo Installer:
echo   %CD%\Output\PremiumClipCutter_Setup.exe
echo ==============================================================
echo.
pause
exit /b 0

:fail
echo.
echo ==============================================================
echo BUILD FAILED. Scroll up to see the exact error.
echo ==============================================================
pause
exit /b 1
