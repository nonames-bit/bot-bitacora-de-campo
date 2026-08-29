@echo off
cd /d "C:\Users\Owner\Documents\projects\finca\2026-08-24-bot-bitacora-de-campo"
C:\Users\Owner\AppData\Local\Programs\Python\Python313\python.exe -m src.watchers.copias_watcher --dir "C:\Usati\Copias" --once >> data\copias_import.log 2>&1

