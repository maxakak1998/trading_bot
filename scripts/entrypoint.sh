#!/bin/bash
# Custom entrypoint to fix pandas compatibility before running freqtrade

# Apply pandas 2.x+ fix for fillna
python3 /scripts/fix_pandas_fillna.py 2>/dev/null || true

# Run freqtrade with all arguments
exec freqtrade "$@"
