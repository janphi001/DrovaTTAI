# XTTS-v2 Worker (Coqui, Idiap-Fork)

Lizenz des Modells: Coqui Public Model License (CPML) – nur nicht-kommerzielle Nutzung.
Vor der ersten Nutzung selbst zustimmen und dann `export COQUI_TOS_AGREED=1` setzen.

uv venv --python 3.11 .venv
uv pip install --python .venv torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
uv pip install --python .venv -r requirements.txt
