#!/usr/bin/env python3
"""
Experiment Tracker - Log and compare hyperopt runs.

Usage:
    python scripts/log_experiment.py --name "baseline_v1" --notes "First run with SMC features"
    python scripts/log_experiment.py --compare  # Show comparison table
"""

import json
import argparse
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

EXPERIMENTS_FILE = Path(__file__).parent.parent / "experiments.json"


def parse_hyperopt_result(log_path: str) -> Dict[str, Any]:
    """Parse hyperopt.log to extract key metrics."""
    metrics = {
        "trades": 0,
        "win_rate": 0.0,
        "total_profit_pct": 0.0,
        "avg_profit_pct": 0.0,
        "drawdown_pct": 0.0,
        "profit_factor": 0.0,
        "long_trades": 0,
        "short_trades": 0,
        "long_profit_pct": 0.0,
        "short_profit_pct": 0.0,
        "best_epoch": 0,
        "epochs_run": 0,
    }
    
    try:
        with open(log_path, 'r') as f:
            content = f.read()
        
        # Parse key metrics using regex
        patterns = {
            "trades": r"Total/Daily Avg Trades\s+│\s+(\d+)",
            "win_rate": r"Win%\s*│[^│]*│\s*[\d.]+\s*│[^│]*│[^│]*│[^│]*│[^│]*│\s*[\d\s]+(\d+)\s*│",
            "total_profit_pct": r"Total profit %\s+│\s+([-\d.]+)%?",
            "drawdown_pct": r"Max % of account underwater\s+│\s+([\d.]+)%?",
            "profit_factor": r"Profit factor\s+│\s+([\d.]+)",
            "long_trades": r"Long / Short trades\s+│\s+(\d+)",
            "short_trades": r"Long / Short trades\s+│\s+\d+\s*/\s*(\d+)",
            "long_profit_pct": r"Long / Short profit %\s+│\s+([-\d.]+)%",
            "short_profit_pct": r"Long / Short profit %\s+│\s+[-\d.]+%\s*/\s*([-\d.]+)%",
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                value = match.group(1)
                if key in ["trades", "long_trades", "short_trades", "best_epoch", "epochs_run"]:
                    metrics[key] = int(value)
                else:
                    metrics[key] = float(value)
        
        # Parse win rate from summary line
        win_match = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)", content)
        if win_match:
            wins = int(win_match.group(1))
            losses = int(win_match.group(3))
            if wins + losses > 0:
                metrics["win_rate"] = (wins / (wins + losses)) * 100
        
    except Exception as e:
        print(f"Warning: Could not parse log: {e}")
    
    return metrics


def load_experiments() -> list:
    """Load existing experiments from JSON file."""
    if EXPERIMENTS_FILE.exists():
        with open(EXPERIMENTS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_experiments(experiments: list):
    """Save experiments to JSON file."""
    with open(EXPERIMENTS_FILE, 'w') as f:
        json.dump(experiments, f, indent=2)


def get_current_config() -> Dict[str, Any]:
    """Get current config flags and hyperopt params."""
    config_path = Path(__file__).parent.parent / "user_data" / "config.json"
    params_path = Path(__file__).parent.parent / "user_data" / "strategies" / "FreqAIStrategy.json"
    
    config = {}
    try:
        with open(config_path, 'r') as f:
            full_config = json.load(f)
            config["flags"] = full_config.get("custom_flags", {})
    except:
        config["flags"] = {}
    
    try:
        with open(params_path, 'r') as f:
            config["params"] = json.load(f)
    except:
        config["params"] = {}
    
    return config


def log_experiment(name: str, notes: str = "", log_path: str = "hyperopt.log"):
    """Log a new experiment."""
    experiments = load_experiments()
    
    # Parse results
    metrics = parse_hyperopt_result(log_path)
    config = get_current_config()
    
    # Get git info
    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()[:8]
        git_branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    except:
        git_hash = "unknown"
        git_branch = "unknown"
    
    experiment = {
        "id": len(experiments) + 1,
        "name": name,
        "timestamp": datetime.now().isoformat(),
        "git_hash": git_hash,
        "git_branch": git_branch,
        "notes": notes,
        "metrics": metrics,
        "config": config,
    }
    
    experiments.append(experiment)
    save_experiments(experiments)
    
    print(f"✅ Logged experiment #{experiment['id']}: {name}")
    print(f"   Win Rate: {metrics['win_rate']:.1f}%")
    print(f"   Profit: {metrics['total_profit_pct']:.2f}%")
    print(f"   Trades: {metrics['trades']} (L:{metrics['long_trades']}/S:{metrics['short_trades']})")


def compare_experiments(last_n: int = 10):
    """Display comparison table of recent experiments."""
    experiments = load_experiments()[-last_n:]
    
    if not experiments:
        print("No experiments logged yet.")
        return
    
    print("\n" + "=" * 100)
    print(f"{'ID':<4} {'Name':<20} {'Win%':<8} {'Profit%':<10} {'Trades':<10} {'DD%':<8} {'PF':<6} {'L/S Ratio':<12}")
    print("=" * 100)
    
    for exp in experiments:
        m = exp["metrics"]
        ls_ratio = f"{m['long_trades']}/{m['short_trades']}"
        
        # Color coding (ANSI)
        win_color = "\033[92m" if m['win_rate'] >= 65 else "\033[91m"
        profit_color = "\033[92m" if m['total_profit_pct'] > 0 else "\033[91m"
        reset = "\033[0m"
        
        print(f"{exp['id']:<4} {exp['name'][:20]:<20} "
              f"{win_color}{m['win_rate']:.1f}%{reset:<8} "
              f"{profit_color}{m['total_profit_pct']:+.2f}%{reset:<10} "
              f"{m['trades']:<10} {m['drawdown_pct']:.1f}%{'':<8} "
              f"{m['profit_factor']:.2f}{'':<6} {ls_ratio:<12}")
    
    print("=" * 100)
    
    # Best experiment
    best = max(experiments, key=lambda x: x['metrics']['win_rate'])
    print(f"\n🏆 Best Win Rate: #{best['id']} {best['name']} ({best['metrics']['win_rate']:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Experiment Tracker")
    parser.add_argument("--name", "-n", help="Experiment name")
    parser.add_argument("--notes", default="", help="Notes about this run")
    parser.add_argument("--log", default="hyperopt.log", help="Path to hyperopt.log")
    parser.add_argument("--compare", "-c", action="store_true", help="Compare experiments")
    parser.add_argument("--last", type=int, default=10, help="Number of experiments to show")
    
    args = parser.parse_args()
    
    if args.compare:
        compare_experiments(args.last)
    elif args.name:
        log_experiment(args.name, args.notes, args.log)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
