python -m pip install --upgrade pip
python -m pip install pip-tools
pip-compile --generate-hashes requirements.in
python -m pip install -r requirements.txt
python -m pytest -q