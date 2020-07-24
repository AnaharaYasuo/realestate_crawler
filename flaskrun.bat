@echo off
call D:\python-env\sumifu\Scripts\activate
start /b python D:\code\git\realestate_crawler\src\function\sumifu\main.py>flask.log

set api_url=%1
@echo on
@echo %api_url%
@echo off

rem flask起動待ち
timeout /t 10 > nul
rem http://127.0.0.1:8000/api/tokyu/mansion/start
start /b curl %api_url%

rem 1.5時間待機待ち
timeout /t 5400 > nul
start /b curl http://127.0.0.1:8000/api/kill
exit
