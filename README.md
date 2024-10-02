# Drift v2 Risk Dashboard


Quick Start:
1. Copy .env.example to .env and set RPC_URL
2. Create new venv `python -m venv .venv`
3. Activate venv `.venv/bin/activate`
4. Install dependencies `pip install -r requirements.txt`
5. Run the frontend with `streamlit run src/main.py`
6. Run the backend with `uvicorn src.main:app --host 0.0.0.0 --port 8000`

Current Metrics:
1. Largest perp positions
2. Largest spot borrows
3. Account health distribution
4. Most levered perp positions > $1m notional
5. Most levered spot borrows > $750k notional
