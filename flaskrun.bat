@echo off
rem実行中の処理を停止させる
rem start /b curl http://127.0.0.1:8000/api/kill

call D:\python-env\sumifu\Scripts\activate
start /b python D:\code\git\realestate_crawler\src\function\sumifu\main.py

set api_url=%1
@echo on
@echo %api_url%
@echo off

rem flask起動待ち
timeout /t 5 > nul
start /b curl %api_url%

rem 30分待機待ち
timeout /t 1800 > nul
start /b curl %api_url%

rem 1時間待機待ち
timeout /t 3600 > nul
rem start /b curl http://127.0.0.1:8000/api/kill
exit
