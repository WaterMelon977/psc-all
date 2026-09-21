@echo off
:: ============================================================
:: exq.bat  --  EXQ APPSC PDF Extractor launcher
:: Drop this folder (exq\bin) into your PATH once and then
:: call:  exq <pdf>  [topics.yaml]  [--output-dir <dir>]
:: ============================================================

setlocal

:: Resolve the real location of this bat file so it works from
:: any working directory once it is on PATH
set "EXQ_BAT_DIR=%~dp0"
set "EXQ_ROOT=%EXQ_BAT_DIR%.."

:: Normalise the path (removes trailing backslash artefacts)
pushd "%EXQ_ROOT%"
set "EXQ_ROOT=%CD%"
popd

:: Default topics file lives next to app.py in the exq root
set "DEFAULT_TOPICS=%EXQ_ROOT%\topics.yaml"

:: Guard: at least one argument (the PDF) must be provided
if "%~1"=="" (
    echo.
    echo  EXQ -- APPSC PDF Question Extractor
    echo  ------------------------------------
    echo  Usage:
    echo    exq ^<pdf^>  [topics.yaml]  [--output-dir ^<dir^>]  [-e ^<exam^>]
    echo.
    echo  Examples:
    echo    exq "2025-GSMA.pdf"
    echo    exq "2025-GSMA.pdf" topics_gsma.yaml
    echo    exq "2025-GSMA.pdf" topics_gsma.yaml -e "2025-GSMA"
    echo    exq "2025-GSMA.pdf" topics_gsma.yaml --output-dir D:\output -e "2025-GSMA"
    echo.
    echo  If topics.yaml is omitted, uses:
    echo    %DEFAULT_TOPICS%
    echo.
    exit /b 1
)

:: Run app.py from the exq root so relative imports work
python "%EXQ_ROOT%\app.py" %*
endlocal
