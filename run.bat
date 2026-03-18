@echo off
title SurveyCAD Converter - Made by Yatna Patel
echo ================================================
echo  SurveyCAD Converter v2
echo  Made by Yatna Patel
echo ================================================
echo.
echo Starting server...
cd /d "%~dp0"
timeout /t 1 /nobreak > nul
start http://localhost:5000
python app.py
pause
