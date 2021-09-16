cd /d %~dp0
del flask.log
call D:\python-env\sumifu\Scripts\activate
start /b python D:\code\git\realestate_crawler\src\function\sumifu\main.py
