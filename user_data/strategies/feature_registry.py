"""
Feature Registry - Version-tracked Feature Flags System
========================================================

Hệ thống quản lý tính năng với version tracking.
Cho phép toggle on/off features và dễ dàng revert về các version trước.

Usage:
    # Trong config.json:
    "freqai": {
        "feature_version": "v1.0_baseline"  # Hoặc specific flags
    }
    
    # Trong strategy:
    from feature_registry import FeatureFlags
    flags = FeatureFlags(config)
    if flags.is_enabled("atr_stoploss"):
        ...
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# FEATURE DEFINITIONS
# ============================================================
# Mỗi feature có metadata để track history và purpose

AVAILABLE_FEATURES: Dict[str, Dict[str, Any]] = {
    # ==================== STOPLOSS FEATURES ====================
    "atr_stoploss": {
        "name": "ATR Dynamic Stoploss",
        "description": "Stoploss dựa trên ATR volatility. High vol = wider SL, Low vol = tighter SL",
        "category": "risk_management",
        "added_in": "v1.0",
        "default": True,
        "conflicts_with": ["fixed_stoploss"]
    },
    "fixed_stoploss": {
        "name": "Fixed 20% Margin Stoploss", 
        "description": "Stoploss cố định = 20% margin loss, tính theo leverage",
        "category": "risk_management",
        "added_in": "v1.1",
        "default": False,
        "conflicts_with": ["atr_stoploss"]
    },
    "trailing_stop": {
        "name": "Trailing Stop",
        "description": "Di chuyển stoploss theo profit để bảo vệ lời",
        "category": "risk_management",
        "added_in": "v1.0",
        "default": False,
        "conflicts_with": []
    },
    
    # ==================== LABELING FEATURES ====================
    "regression_labels": {
        "name": "Regression Labeling",
        "description": "Target = % price change trong N candles tới",
        "category": "labeling",
        "added_in": "v1.0",
        "default": True,
        "conflicts_with": ["trend_scanning"]
    },
    "trend_scanning": {
        "name": "Trend Scanning Labeling",
        "description": "Dùng t-statistics để xác định xu hướng có ý nghĩa thống kê",
        "category": "labeling",
        "added_in": "v1.1",
        "default": False,
        "conflicts_with": ["regression_labels"]
    },
    
    # ==================== ENTRY FILTERS ====================
    "regime_filter": {
        "name": "Market Regime Filter",
        "description": "Không trade khi market regime = VOLATILE hoặc EXTREME",
        "category": "entry_filter",
        "added_in": "v1.0",
        "default": True,
        "conflicts_with": []
    },
    "confluence_filter": {
        "name": "Confluence Score Filter",
        "description": "Yêu cầu overall_score > threshold để entry",
        "category": "entry_filter",
        "added_in": "v1.0",
        "default": True,
        "conflicts_with": []
    },
    "trend_filter": {
        "name": "EMA 200 Trend Filter",
        "description": "Long khi price > EMA200, Short khi price < EMA200",
        "category": "entry_filter",
        "added_in": "v1.0",
        "default": True,
        "conflicts_with": []
    },
    "structure_filter": {
        "name": "SMC Structure Filter",
        "description": "Requires Order Block, Wyckoff Spring/Upthrust, or VSA Divergence confirmation",
        "category": "entry_filter",
        "added_in": "v2.0",
        "default": False,
        "conflicts_with": []
    },
    
    # ==================== ML FEATURES ====================
    "pca": {
        "name": "PCA Dimensionality Reduction",
        "description": "Giảm chiều dữ liệu để tránh overfitting",
        "category": "ml_optimization",
        "added_in": "v1.1",
        "default": False,
        "conflicts_with": []
    },
    "noise_regularization": {
        "name": "Noise Regularization",
        "description": "Thêm noise vào features để tăng robustness",
        "category": "ml_optimization",
        "added_in": "v1.1",
        "default": False,
        "conflicts_with": []
    },
}

# ============================================================
# VERSION PRESETS
# ============================================================
# Predefined feature combinations với performance history

VERSION_PRESETS: Dict[str, Dict[str, Any]] = {
    "v1.0_baseline": {
        "description": "Best run 12/05/2025 - +4.86% profit, 43.6% WR",
        "release_date": "2025-12-05",
        "performance": {
            "profit_pct": 4.86,
            "win_rate": 43.6,
            "total_trades": 78,
            "max_drawdown": 5.33
        },
        "features": [
            "atr_stoploss",
            "regression_labels",
            "regime_filter",
            "confluence_filter",
            "trend_filter"
        ]
    },
    "v1.1_experimental": {
        "description": "Trend Scanning + Fixed SL experiment",
        "release_date": "2025-12-06",
        "performance": {
            "profit_pct": 2.39,
            "win_rate": 42.0,
            "total_trades": 69,
            "max_drawdown": 5.23
        },
        "features": [
            "fixed_stoploss",
            "trend_scanning",
            "regime_filter",
            "confluence_filter",
            "trend_filter",
            "pca",
            "noise_regularization"
        ]
    },
}


class FeatureFlags:
    """
    Feature Flags Manager với version tracking.
    
    Usage:
        flags = FeatureFlags(config)
        
        # Check single feature
        if flags.is_enabled("atr_stoploss"):
            ...
        
        # Get all enabled features
        enabled = flags.get_enabled_features()
        
        # Log status
        flags.log_status()
    """
    
    def __init__(self, config: dict):
        """
        Initialize từ Freqtrade config.
        
        Ưu tiên:
        1. feature_flags dict trong config (explicit)
        2. feature_version preset trong config
        3. Default values từ AVAILABLE_FEATURES
        """
        self.config = config
        self._enabled_features: Dict[str, bool] = {}
        self._version: str = "custom"
        
        self._load_features()
        self._validate_conflicts()
        
    def _load_features(self) -> None:
        """Load features từ config hoặc preset."""
        freqai_config = self.config.get("freqai", {})
        
        # Check for explicit feature_flags
        explicit_flags = freqai_config.get("feature_flags", {})
        
        # Check for version preset
        version_preset = freqai_config.get("feature_version", None)
        
        if explicit_flags:
            # Use explicit flags với defaults
            self._version = "custom"
            for feature_name, feature_info in AVAILABLE_FEATURES.items():
                self._enabled_features[feature_name] = explicit_flags.get(
                    feature_name, feature_info["default"]
                )
                
        elif version_preset and version_preset in VERSION_PRESETS:
            # Use preset
            self._version = version_preset
            preset = VERSION_PRESETS[version_preset]
            enabled_list = preset["features"]
            
            for feature_name in AVAILABLE_FEATURES:
                self._enabled_features[feature_name] = feature_name in enabled_list
                
        else:
            # Use defaults
            self._version = "default"
            for feature_name, feature_info in AVAILABLE_FEATURES.items():
                self._enabled_features[feature_name] = feature_info["default"]
    
    def _validate_conflicts(self) -> None:
        """Check và warn về conflicting features."""
        enabled = self.get_enabled_features()
        
        for feature_name in enabled:
            conflicts = AVAILABLE_FEATURES[feature_name].get("conflicts_with", [])
            for conflict in conflicts:
                if conflict in enabled:
                    logger.warning(
                        f"⚠️ Feature conflict: '{feature_name}' và '{conflict}' "
                        f"không nên enable cùng lúc!"
                    )
    
    def is_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled."""
        if feature_name not in AVAILABLE_FEATURES:
            logger.warning(f"Unknown feature: {feature_name}")
            return False
        return self._enabled_features.get(feature_name, False)
    
    def get_enabled_features(self) -> List[str]:
        """Get list of all enabled features."""
        return [f for f, enabled in self._enabled_features.items() if enabled]
    
    def get_disabled_features(self) -> List[str]:
        """Get list of all disabled features."""
        return [f for f, enabled in self._enabled_features.items() if not enabled]
    
    def get_version(self) -> str:
        """Get current version/preset name."""
        return self._version
    
    def get_version_info(self) -> Optional[Dict]:
        """Get version preset info if using a preset."""
        if self._version in VERSION_PRESETS:
            return VERSION_PRESETS[self._version]
        return None
    
    def log_status(self) -> None:
        """Log current feature status."""
        enabled = self.get_enabled_features()
        disabled = self.get_disabled_features()
        
        logger.info("=" * 60)
        logger.info(f"📋 FEATURE FLAGS - Version: {self._version}")
        logger.info("=" * 60)
        
        if self._version in VERSION_PRESETS:
            info = VERSION_PRESETS[self._version]
            logger.info(f"   Description: {info['description']}")
            perf = info.get("performance", {})
            if perf:
                logger.info(f"   Performance: +{perf['profit_pct']}% | WR: {perf['win_rate']}%")
        
        logger.info(f"✅ Enabled ({len(enabled)}): {', '.join(enabled)}")
        logger.info(f"❌ Disabled ({len(disabled)}): {', '.join(disabled)}")
        logger.info("=" * 60)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export current flags as dict (for logging/saving)."""
        return {
            "version": self._version,
            "timestamp": datetime.now().isoformat(),
            "features": self._enabled_features.copy()
        }


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def list_available_features() -> None:
    """Print all available features grouped by category."""
    from collections import defaultdict
    
    by_category = defaultdict(list)
    for name, info in AVAILABLE_FEATURES.items():
        by_category[info["category"]].append((name, info))
    
    print("\n" + "=" * 60)
    print("📋 AVAILABLE FEATURES")
    print("=" * 60)
    
    for category, features in sorted(by_category.items()):
        print(f"\n[{category.upper()}]")
        for name, info in features:
            default = "✅" if info["default"] else "❌"
            print(f"  {default} {name}: {info['description'][:50]}...")


def list_version_presets() -> None:
    """Print all available version presets."""
    print("\n" + "=" * 60)
    print("🏷️ VERSION PRESETS")
    print("=" * 60)
    
    for version, info in VERSION_PRESETS.items():
        perf = info.get("performance", {})
        print(f"\n{version}: {info['description']}")
        if perf:
            print(f"   Profit: +{perf['profit_pct']}% | WR: {perf['win_rate']}% | Trades: {perf['total_trades']}")
        print(f"   Features: {', '.join(info['features'])}")


if __name__ == "__main__":
    # Test
    list_available_features()
    list_version_presets()
