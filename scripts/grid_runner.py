#!/usr/bin/env python3
"""
Grid Search Runner - Execute pre-defined test configurations.

Usage:
    python scripts/grid_runner.py --list                    # List available tests
    python scripts/grid_runner.py --run "Quick Sanity"     # Run specific test locally
    python scripts/grid_runner.py --run-gcp "SMC Optimal"  # Run on GCP VM
    python scripts/grid_runner.py --apply-features smc_focus  # Apply feature set to config
"""

import json
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

GRID_CONFIG_PATH = Path(__file__).parent / "grid_configs" / "grid_config.json"
CONFIG_PATH = Path(__file__).parent.parent / "user_data" / "config.json"
MAKEFILE_PATH = Path(__file__).parent.parent / "Makefile"


def load_grid_config() -> Dict[str, Any]:
    """Load grid configuration."""
    with open(GRID_CONFIG_PATH, 'r') as f:
        return json.load(f)


def load_config() -> Dict[str, Any]:
    """Load user config.json."""
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def save_config(config: Dict[str, Any]):
    """Save user config.json."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def list_tests():
    """List available grid tests."""
    grid = load_grid_config()
    
    print("\n" + "=" * 70)
    print("Available Grid Tests")
    print("=" * 70)
    
    for test in grid["recommended_tests"]:
        print(f"\n📋 {test['name']}")
        print(f"   Timerange: {test['timerange']}")
        print(f"   Epochs: {test['epochs']}")
        print(f"   Spaces: {test['spaces']}")
        print(f"   Features: {test['feature_set']}")
        print(f"   Est. Time: {test['estimated_time']}")
    
    print("\n" + "=" * 70)
    print("\nFeature Sets:")
    for fs in grid["grid_dimensions"]["feature_sets"]:
        enabled = sum(1 for v in fs["flags"].values() if v)
        total = len(fs["flags"])
        print(f"  • {fs['id']}: {fs['description']} ({enabled}/{total} enabled)")


def get_test_config(test_name: str) -> Optional[Dict[str, Any]]:
    """Get test configuration by name."""
    grid = load_grid_config()
    
    for test in grid["recommended_tests"]:
        if test["name"].lower() == test_name.lower():
            return test
    
    return None


def get_timerange(timerange_id: str) -> str:
    """Get timerange string from ID."""
    grid = load_grid_config()
    
    for tr in grid["grid_dimensions"]["timeranges"]:
        if tr["id"] == timerange_id:
            return tr["range"]
    
    return timerange_id  # Return as-is if not found


def get_spaces(spaces_id: str) -> str:
    """Get spaces string from ID."""
    grid = load_grid_config()
    
    for sp in grid["grid_dimensions"]["spaces"]:
        if sp["id"] == spaces_id:
            return sp["value"]
    
    return spaces_id  # Return as-is if not found


def get_feature_set(feature_set_id: str) -> Optional[Dict[str, bool]]:
    """Get feature flags from feature set ID."""
    grid = load_grid_config()
    
    for fs in grid["grid_dimensions"]["feature_sets"]:
        if fs["id"] == feature_set_id:
            return fs["flags"]
    
    return None


def apply_feature_set(feature_set_id: str):
    """Apply a feature set to config.json."""
    flags = get_feature_set(feature_set_id)
    
    if not flags:
        print(f"❌ Feature set '{feature_set_id}' not found")
        return False
    
    config = load_config()
    config["custom_flags"] = {**config.get("custom_flags", {}), **flags}
    save_config(config)
    
    enabled = sum(1 for v in flags.values() if v)
    print(f"✅ Applied feature set '{feature_set_id}' ({enabled} features enabled)")
    return True


def run_test_local(test_name: str):
    """Run a grid test locally."""
    test = get_test_config(test_name)
    
    if not test:
        print(f"❌ Test '{test_name}' not found. Use --list to see available tests.")
        return
    
    print(f"\n🧪 Running Grid Test: {test['name']}")
    print("=" * 50)
    
    # Apply feature set
    if not apply_feature_set(test["feature_set"]):
        return
    
    # Build command
    timerange = get_timerange(test["timerange"])
    spaces = get_spaces(test["spaces"])
    epochs = test["epochs"]
    
    cmd = [
        "make", "hyperopt",
        f"HYPEROPT_EPOCHS={epochs}",
        f"TRAIN_TIMERANGE={timerange}",
        f"HYPEROPT_SPACES={spaces}"
    ]
    
    print(f"\n📝 Command: {' '.join(cmd)}")
    print(f"⏱️  Estimated time: {test['estimated_time']}")
    print("\nStarting...\n")
    
    # Run
    subprocess.run(cmd, cwd=Path(__file__).parent.parent)


def run_test_gcp(test_name: str):
    """Run a grid test on GCP VM."""
    test = get_test_config(test_name)
    
    if not test:
        print(f"❌ Test '{test_name}' not found. Use --list to see available tests.")
        return
    
    print(f"\n🚀 Running Grid Test on GCP: {test['name']}")
    print("=" * 50)
    
    # Step 1: Apply feature set locally
    if not apply_feature_set(test["feature_set"]):
        return
    
    # Step 2: Commit and sync
    print("\n[1/3] Committing and syncing code...")
    subprocess.run(["git", "add", "."], cwd=Path(__file__).parent.parent)
    subprocess.run(
        ["git", "commit", "-m", f"Grid test: {test['name']}"],
        cwd=Path(__file__).parent.parent
    )
    subprocess.run(["git", "push"], cwd=Path(__file__).parent.parent)
    
    # Step 3: Start VM and sync
    print("\n[2/3] Starting VM and syncing...")
    subprocess.run(["make", "gcp-start"], cwd=Path(__file__).parent.parent)
    subprocess.run(["make", "gcp-sync"], cwd=Path(__file__).parent.parent)
    
    # Step 4: Run hyperopt via setsid
    timerange = get_timerange(test["timerange"])
    epochs = test["epochs"]
    
    print(f"\n[3/3] Starting hyperopt on GCP...")
    print(f"      Epochs: {epochs}")
    print(f"      Timerange: {timerange}")
    print(f"      Est. Time: {test['estimated_time']}")
    
    ssh_cmd = f"""
    gcloud compute ssh trading-bot --zone=asia-southeast1-b --command="cd /opt/freqtrade && setsid /opt/freqtrade/run_hyperopt_flow.sh {epochs} {timerange} </dev/null >/opt/freqtrade/flow_debug.log 2>&1 &"
    """
    
    subprocess.run(ssh_cmd, shell=True)
    
    print("\n✅ Grid test submitted to GCP!")
    print("   VM will auto-shutdown when complete.")
    print("   Monitor with: make gcp-status")


def main():
    parser = argparse.ArgumentParser(description="Grid Search Runner")
    parser.add_argument("--list", "-l", action="store_true", help="List available tests")
    parser.add_argument("--run", help="Run a test locally")
    parser.add_argument("--run-gcp", help="Run a test on GCP VM")
    parser.add_argument("--apply-features", help="Apply a feature set to config")
    
    args = parser.parse_args()
    
    if args.list:
        list_tests()
    elif args.run:
        run_test_local(args.run)
    elif args.run_gcp:
        run_test_gcp(args.run_gcp)
    elif args.apply_features:
        apply_feature_set(args.apply_features)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
