@echo off
title Procurement Agent
cd /d "%~dp0"
start "" "dist\procurement.exe" --gui
exit
