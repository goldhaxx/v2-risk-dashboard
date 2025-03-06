#!/bin/bash
set -e

python -m backend.scripts.generate_ucache \
    asset-liability \
    --mode 0 \
    --perp-market-index 0

python -m backend.scripts.generate_ucache \
    price-shock \
    --asset-group "ignore+stables" \
    --oracle-distortion 0.05 \
    --n-scenarios 5

python -m backend.scripts.generate_ucache \
    price-shock \
    --asset-group "jlp+only" \
    --oracle-distortion 0.05 \
    --n-scenarios 5

python -m backend.scripts.generate_ucache \
    price-shock \
    --asset-group "ignore+stables" \
    --oracle-distortion 0.1 \
    --n-scenarios 10

# Delete old pickles
cd pickles && ls -t | tail -n +4 | xargs rm -rf