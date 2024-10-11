@echo on
call .venv\Scripts\activate
start http://0.0.0.0:8000/app/orders/
python3 manage.py runserver
pause 