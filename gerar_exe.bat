@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo  GERANDO EXECUTAVEL - CONTROLE DE ESTOQUE
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python e marque Add Python to PATH.
    pause
    exit /b 1
)

echo Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Erro ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo Limpando builds antigos...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q Controle_Estoque.spec 2>nul

echo.
echo Gerando .exe...
python -m PyInstaller --noconfirm --clean --windowed --name "Controle_Estoque" main.py
if errorlevel 1 (
    echo Erro ao gerar o executavel.
    pause
    exit /b 1
)

copy /Y estoque.db "dist\Controle_Estoque\estoque.db" >nul

echo.
echo ==========================================
echo  PRONTO!
echo  Abra: dist\Controle_Estoque\Controle_Estoque.exe
echo ==========================================
pause
