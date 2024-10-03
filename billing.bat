@echo on
.venv\\Scripts\\activate
start http://127.0.0.1:8000/app/orders/
python3 manage.py runserver
pause 