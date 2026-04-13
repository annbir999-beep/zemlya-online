@echo off
chcp 65001 > nul
python "%~dp0enrich_local.py" >> "%~dp0enrich.log" 2>&1
