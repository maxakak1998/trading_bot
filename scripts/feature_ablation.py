#!/usr/bin/env python3
"""
Feature Ablation Testing - Systematically toggle features to find best combination.

Usage:
    python scripts/feature_ablation.py --list              # List all features
    python scripts/feature_ablation.py --toggle vsa        # Toggle VSA feature
    python scripts/feature_ablation.py --run-all           # Run ablation on all features
    python scripts/feature_ablation.py --restore           # Restore original config
"""

import json
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

CONFIG_PATH = Path(__file__).parent.parent / "user_data" / "config.json"
BACKUP_PATH = Path(__file__).parent.parent / "user_data" / "config.backup.json"
ABLATION_RESULTS = Path(__file__).parent.parent / "ablation_results.json"


# Features to test during ablation
ABLATION_FEATURES = [
    "vsa",              # VSA Indicators
    "smc",              # SMC Indicators  
    "wave",             # Wave/Fibonacci Indicators
    "chart_patterns",   # Chart Pattern Recognition
    "trailing_stop",    # Trailing Stop
    "regime_filter",    # Market Regime Filter
    "confluence_filter", # Confluence Filter
    "trend_filter",     # EMA Trend Filter
    "pca",              # PCA Dimensionality Reduction
    "noise_regularization", # Noise Regularization
    "htf_ob_confluence", # HTF Order Block Confluence
]


def load_config() -> Dict[str, Any]:
    """Load config.json."""
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def save_config(config: Dict[str, Any]):
    """Save config.json."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def backup_config():
    """Backup original config."""
    if not BACKUP_PATH.exists():
        shutil.copy(CONFIG_PATH, BACKUP_PATH)
        print(f"✅ Backed up config to {BACKUP_PATH}")


def restore_config():
    """Restore config from backup."""
    if BACKUP_PATH.exists():
        shutil.copy(BACKUP_PATH, CONFIG_PATH)
        print(f"✅ Restored config from backup")
    else:
        print("❌ No backup found")


def list_features():
    """List all features and their current status."""
    config = load_config()
    flags = config.get("custom_flags", {})
    
    print("\n" + "=" * 50)
    print("Feature Flags Status")
    print("=" * 50)
    
    for feature in ABLATION_FEATURES:
        status = flags.get(feature, False)
        icon = "✅" if status else "❌"
        print(f"{icon} {feature}: {status}")
    
    print("=" * 50)


def toggle_feature(feature: str) -> bool:
    """Toggle a single feature and return new state."""
    config = load_config()
    
    if "custom_flags" not in config:
        config["custom_flags"] = {}
    
    current = config["custom_flags"].get(feature, False)
    config["custom_flags"][feature] = not current
    
    save_config(config)
    
    new_state = "ON" if not current else "OFF"
    print(f"🔄 Toggled {feature}: {new_state}")
    
    return not current


def set_feature(feature: str, enabled: bool):
    """Set a feature to specific state."""
    config = load_config()
    
    if "custom_flags" not in config:
        config["custom_flags"] = {}
    
    config["custom_flags"][feature] = enabled
    save_config(config)


def run_quick_test() -> Dict[str, Any]:
    """Run quick hyperopt test (1 epoch, 1 day) and return results."""
    cmd = [
        "make", "hyperopt",
        "HYPEROPT_EPOCHS=1",
        "TRAIN_TIMERANGE=20240101-20240102"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
            cwd=Path(__file__).parent.parent
        )
        
        # Check if it ran successfully (no Python errors)
        if result.returncode == 0 and "Error" not in result.stderr:
            return {"success": True, "output": result.stdout}
        else:
            return {"success": False, "error": result.stderr}
    
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_ablation_all():
    """Run ablation study on all features."""
    backup_config()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "baseline": None,
        "ablations": []
    }
    
    print("\n🔬 Starting Feature Ablation Study...")
    print("=" * 60)
    
    # Step 1: Get baseline (all current features)
    print("\n[1] Running baseline test...")
    baseline_result = run_quick_test()
    results["baseline"] = {
        "success": baseline_result["success"],
        "config": load_config().get("custom_flags", {})
    }
    
    if not baseline_result["success"]:
        print(f"❌ Baseline failed: {baseline_result.get('error', 'Unknown')}")
        restore_config()
        return
    
    print("✅ Baseline passed")
    
    # Step 2: Toggle each feature and test
    config = load_config()
    original_flags = config.get("custom_flags", {}).copy()
    
    for i, feature in enumerate(ABLATION_FEATURES, 1):
        print(f"\n[{i+1}] Testing with {feature} toggled...")
        
        # Toggle feature
        current_state = original_flags.get(feature, False)
        set_feature(feature, not current_state)
        
        # Run test
        test_result = run_quick_test()
        
        ablation = {
            "feature": feature,
            "original_state": current_state,
            "toggled_state": not current_state,
            "success": test_result["success"],
        }
        
        if test_result["success"]:
            print(f"✅ {feature} toggle test passed")
        else:
            print(f"❌ {feature} toggle test failed")
            ablation["error"] = test_result.get("error", "Unknown")
        
        results["ablations"].append(ablation)
        
        # Restore to original state
        set_feature(feature, current_state)
    
    # Save results
    with open(ABLATION_RESULTS, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"✅ Ablation study complete! Results saved to {ABLATION_RESULTS}")
    
    # Summary
    passed = sum(1 for a in results["ablations"] if a["success"])
    total = len(results["ablations"])
    print(f"\nSummary: {passed}/{total} feature toggles passed")
    
    # Restore original config
    restore_config()


def main():
    parser = argparse.ArgumentParser(description="Feature Ablation Testing")
    parser.add_argument("--list", "-l", action="store_true", help="List all features")
    parser.add_argument("--toggle", "-t", help="Toggle a specific feature")
    parser.add_argument("--enable", help="Enable a specific feature")
    parser.add_argument("--disable", help="Disable a specific feature")
    parser.add_argument("--run-all", action="store_true", help="Run ablation on all features")
    parser.add_argument("--restore", "-r", action="store_true", help="Restore config from backup")
    parser.add_argument("--backup", "-b", action="store_true", help="Backup current config")
    
    args = parser.parse_args()
    
    if args.list:
        list_features()
    elif args.toggle:
        toggle_feature(args.toggle)
    elif args.enable:
        set_feature(args.enable, True)
        print(f"✅ Enabled {args.enable}")
    elif args.disable:
        set_feature(args.disable, False)
        print(f"❌ Disabled {args.disable}")
    elif args.run_all:
        run_ablation_all()
    elif args.restore:
        restore_config()
    elif args.backup:
        backup_config()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
