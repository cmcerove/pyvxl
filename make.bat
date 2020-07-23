@ECHO OFF

SET MODULE=pyvxl

:: "Makefile" for Windows
set "installDir=.\lib"
set "inspy=0"
set "inseasy=0"
set "inspip=0"
set "ins=0"

if "%1" == "" GOTO check_python
if "%1" == "setup" GOTO check_python
if "%1" == "develop" GOTO setup_develop
if "%1" == "doc" GOTO doc
if "%1" == "test" GOTO test
if "%1" == "coverage" GOTO coverage
if "%1" == "clean" GOTO clean
GOTO help

:check_python
rem TODO: Change this to an exe that checks the latest version of python 3
rem       is installed. If it isn't installed, it will download and install it.
rem if %ins%==1 PAUSE
rem set "ins=0"
rem set "arch=False"
rem if not exist "C:\Python27\python.exe" (
rem     GOTO python
rem     set "arch=True"
rem ) else (
rem     :: Check that python is 32bit
rem     for /f %%i in ('C:\Python27\python.exe -c "import platform;print bool(platform.architecture()[0] == '32bit')"') do (set "arch=%%i")
rem )
rem if %arch% == False GOTO arch_error
rem if not exist "C:\Python27\Scripts\pip.exe" GOTO pip
rem if not exist "C:\Python27\Scripts\easy_install.exe" GOTO easyinstall
GOTO check_path

:python
echo.
if %inspy% == 1 GOTO end
echo.Installing python...
%installDir%\python-2.7.5.msi
IF ERRORLEVEL 1 GOTO python_error
echo.python installed successfully.
set "inspy=1"
rem Windows XP does not have setx
if exist %SystemRoot%\system32\setx.exe GOTO check_python
echo.
echo.On Windows XP "C:\Python27;C:\Python27\Scripts;" has to be appended to the PATH environment variable.
GOTO check_python

:easyinstall
if %inseasy% == 1 GOTO end
echo.Adding python to environment variables...
echo.
echo.Installing setuptools...
call %installDir%\setuptools-0.6c11.win32-py2.7.exe
IF ERRORLEVEL 1 GOTO setup_error
echo.setuptools installed successfully.
echo.
set "inseasy=1"
set "ins=1"
GOTO check_python

:pip
if %inspip%==1 GOTO end
echo.
echo.Installing pip...
call %installDir%\pip-1.5.4.win32-py2.7.exe
IF ERRORLEVEL 1 GOTO pip_error
echo.pip installed successfully.
echo.
set "inspip=1"
set "ins=1"
GOTO check_python

:check_path
rem TODO: This check should also be done in the exe for downloading/installing
rem       python.
rem echo.
rem reg query HKEY_CURRENT_USER\Environment /v "path" > nul 2>&1
rem if errorlevel 1 goto nopath
rem set "test="
rem for /f "tokens=*" %%i in ('reg query HKEY_CURRENT_USER\Environment /v "path"') do (
rem     set "test=%test%%%i"
rem )
rem set "test=%test:~18%"
rem set "searchVal=python27"
rem @setlocal enableextensions enabledelayedexpansion
rem if not "x!test:%searchVal%=!"=="x%test%" GOTO setup
rem endlocal
rem echo.Adding python to environment variables...
rem echo.
rem setx PATH "C:\Python27;C:\Python27\Scripts;%test%;"
rem rem Backward compatibility for Windows XP
rem set "PATH=C:\Python27;C:\Python27\Scripts;%test%;"
rem echo.
GOTO setup

:nopath
echo.
echo.Adding python to environment variables...
setx PATH "C:\Python27;C:\Python27\Scripts;"
rem Backward compatibility for Windows XP
set "PATH=C:\Python27;C:\Python27\Scripts;"
echo.
GOTO setup

:setup
ECHO.
ECHO.Installing %MODULE%...
ECHO.
call pip3 install .
IF ERRORLEVEL 1 GOTO setup_error
ECHO.
ECHO.%MODULE% installed correctly
echo.
ECHO.
GOTO clean

:setup_develop
ECHO.
ECHO.Installing %MODULE% for development...
ECHO.
call pip3 install -e .
IF ERRORLEVEL 1 GOTO setup_error
ECHO.
ECHO.%MODULE% installed correctly
echo.
ECHO.
GOTO clean_develop

:doc
ECHO.
ECHO.Generating documentation...
ECHO.
C:\Python27\python.exe C:\Python27\Scripts\epydoc.py -v --config setup.cfg
START ..\documentation\apidocs\index.html
IF ERRORLEVEL 1 GOTO error
GOTO end

:test
ECHO.
ECHO.Running unit and integration tests...
ECHO.
nosetests --stop
IF ERRORLEVEL 1 GOTO error
GOTO end

:coverage
ECHO.
ECHO.Opening coverage report...
ECHO.
START cover\index.html
GOTO end

:clean
call python -c "import time; time.sleep(0.2)"
DEL %MODULE%\*.pyc 2>NUL
RD /s/q dist 2>NUL
RD /s/q %MODULE%.egg-info 2>NUL
RD /s/q build 2>NUL
GOTO end

:clean_develop
call python -c "import time; time.sleep(0.2)"
DEL %MODULE%\*.pyc 2>NUL
RD /s/q dist 2>NUL
RD /s/q build 2>NUL
GOTO end

:help
echo.No rule to make target '%1'
goto error

:arch_error
echo.
echo.64bit Python installation found!
echo.Please uninstall python and rerun the batch file
echo.
PAUSE
goto error

:setup_error
echo.
echo.%MODULE% did not install successfully.
echo.
echo.Try reruning the batch file.
echo.
PAUSE
GOTO error

:python_error
echo.
echo.python did not install successfully.
echo.
PAUSE
GOTO error

:setup_error
echo.
echo.setuptools did not install successfully.
echo.
PAUSE
GOTO error

:pip_error
echo.
echo.pip did not install successfully.
echo.
PAUSE
GOTO error

:error
exit /b 1


:end
exit /b 0
