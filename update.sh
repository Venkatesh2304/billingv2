git stash
git pull --ff
bash
source .venv/Scripts/activate
pip install -r requirements.txt
python3 manage.py migrate
