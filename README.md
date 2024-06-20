# Drift v2 Risk Dashboard


Quick Start:
1. Run `export RPC_URL"YOUR_RPC_HERE"` in terminal for static RPC
2. Create new venv `python3 -m venv venv`
3. Activate venv `source venv/bin/activate`
4. Install dependencies `pip install -r requirements.txt`
5. `streamlit run src/main.py`

Current Metrics:
1. Largest perp positions
2. Largest spot borrows
3. Account health distribution
4. Most levered perp positions > $1m notional
5. Most levered spot borrows > $750k notional

WIP Metrics:
