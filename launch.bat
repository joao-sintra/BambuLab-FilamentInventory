@echo off
cd /d "%~dp0"
set PYTHONPATH=src
start "Filament Inventory Sync" py -3.12 -m bambu_inventory.main
timeout /t 3 /nobreak >nul
start "" "%~dp0filament_inventory.xlsx"
