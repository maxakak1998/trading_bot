#!/usr/bin/env python3
"""
Fix for pandas 2.x+ fillna compatibility issue in FreqTrade.

This script patches the strategy_helper.py file in FreqTrade to fix
the fillna() method that breaks with pandas 2.x+

The issue is at line 109 in strategy_helper.py:
    .fillna(matching_informative_raws.iloc[-1])

In pandas 2.x+, fillna() with a Series/dict containing non-scalar values fails.
We need to iterate and fill column by column.
"""
import sys

# Path to FreqTrade strategy_helper.py
FILEPATH = '/freqtrade/freqtrade/strategy/strategy_helper.py'

# Pattern 1: Original code (unpatched)
OLD_CODE_1 = '''                dataframe.loc[: first_valid_idx - 1] = dataframe.loc[
                        : first_valid_idx - 1
                    ].fillna(matching_informative_raws.iloc[-1])'''

# Pattern 2: First fix attempt (also broken)
OLD_CODE_2 = '''                # Fixed for pandas 2.x+ compatibility
                    fill_values = matching_informative_raws.iloc[-1].to_dict()
                    dataframe.loc[: first_valid_idx - 1] = dataframe.loc[
                        : first_valid_idx - 1
                    ].fillna(value=fill_values)'''

# Fixed code (proper pandas 2.x+ compatible)
NEW_CODE = '''                # Fixed for pandas 2.x+ compatibility
                    # Fill each column individually to handle non-scalar values
                    fill_row = matching_informative_raws.iloc[-1]
                    subset = dataframe.loc[: first_valid_idx - 1].copy()
                    for col in subset.columns:
                        if col in fill_row.index:
                            fill_val = fill_row[col]
                            # Skip non-scalar values (e.g., arrays, lists)
                            try:
                                if subset[col].isna().any():
                                    subset[col] = subset[col].fillna(fill_val)
                            except (TypeError, ValueError):
                                pass
                    dataframe.loc[: first_valid_idx - 1] = subset'''

def main():
    try:
        with open(FILEPATH, 'r') as f:
            content = f.read()
        
        patched = False
        
        # Check if already properly patched
        if "for col in subset.columns:" in content:
            print(f"✅ File already patched: {FILEPATH}")
            return 0
        
        # Try pattern 2 first (our first fix attempt)
        if OLD_CODE_2 in content:
            content = content.replace(OLD_CODE_2, NEW_CODE)
            patched = True
        # Then try original pattern
        elif OLD_CODE_1 in content:
            content = content.replace(OLD_CODE_1, NEW_CODE)
            patched = True
        
        if patched:
            with open(FILEPATH, 'w') as f:
                f.write(content)
            print(f"✅ Successfully patched {FILEPATH}")
            return 0
        else:
            print(f"⚠️ Could not find code to patch in {FILEPATH}")
            print("The code structure may have changed.")
            return 1
    except Exception as e:
        print(f"❌ Error patching file: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
