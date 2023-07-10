@ECHO OFF

SET MODULE=pyvxl

:: "Makefile" for Windows
set "installDir=.\lib"
set "inspy=0"
set "inseasy=0"
set "inspip=0"
set "ins=0"

if "%1" == "" GOTO setup
if "%1" == "develop" GOTO setup_develop
if "%1" == "doc" GOTO doc
if "%1" == "clean" GOTO clean
GOTO help

:setup
ECHO.
ECHO.Installing %MODULE%...
ECHO.
call pip3 install .
IF ERRORLEVEL 1 GOTO setup_error
GOTO clean

:setup_develop
ECHO.
ECHO.Installing %MODULE% for development...
ECHO.
call pip3 install -e .
IF ERRORLEVEL 1 GOTO setup_error
GOTO clean_develop

:clean
call python -c "import time; time.sleep(0.2)"
DEL %MODULE%\*.pyc 2>NUL
RD /s/q dist 2>NUL
RD /s/q %MODULE%.egg-info 2>NUL
RD /s/q build 2>NUL
GOTO post_install

:clean_develop
call python -c "import time; time.sleep(0.2)"
DEL %MODULE%\*.pyc 2>NUL
RD /s/q dist 2>NUL
RD /s/q build 2>NUL
GOTO post_install

:post_install
ECHO.
ECHO.Checking for the XL Driver Library...
ECHO.
call python post_install.py
IF ERRORLEVEL 1 GOTO setup_error
GOTO end

:help
echo.No rule to make target '%1'
goto error

:setup_error
echo.
echo.%MODULE% did not install successfully.
echo.
echo.Try reruning the batch file.
echo.
PAUSE
GOTO error

:error
exit /b 1

:end
ECHO.
ECHO.%MODULE% installed correctly
echo.
ECHO.
exit /b 0
