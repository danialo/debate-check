"""
Configuration management for the claim extraction pipeline
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "preprocessing": {
        "remove_stage_directions": True,
        "remove_timestamps": True,
        "normalize_speaker_names": True
    },
    "segmentation": {
        "use_spacy": True,
        "context_window": 1
    },
    "claim_detection": {
        "statistical": {
            "enabled": True,
            "base_confidence": 0.6,
            "keyword_bonus": 0.2
        },
        "causal": {
            "enabled": True,
            "base_confidence": 0.5,
            "strong_keyword_bonus": 0.2
        },
        "comparative": {
            "enabled": True,
            "base_confidence": 0.5,
            "pattern_bonus": 0.15
        },
        "historical": {
            "enabled": True,
            "base_confidence": 0.4,
            "time_reference_bonus": 0.2
        },
        "factual": {
            "enabled": True,
            "base_confidence": 0.4,
            "uncertainty_penalty": 0.1,
            "certainty_bonus": 0.05,
            "min_confidence": 0.3
        }
    },
    "postprocessing": {
        "remove_duplicates": True,
        "merge_overlapping": True,
        "add_context": True,
        "overlap_threshold": 0.5
    }
}


class ConfigManager:
    """Manages configuration for the claim extraction pipeline"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to YAML config file, if None uses defaults
        """
        self.config = DEFAULT_CONFIG.copy()
        
        if config_path and config_path.exists():
            self.load_config(config_path)
        elif config_path:
            logger.warning(f"Config file not found: {config_path}, using defaults")
    
    def load_config(self, config_path: Path) -> None:
        """Load configuration from YAML file."""
        if not YAML_AVAILABLE:
            logger.error("PyYAML not available, cannot load config file")
            return
        
        try:
            with open(config_path, 'r') as f:
                file_config = yaml.safe_load(f)
            
            # Deep merge with default config
            self.config = self._merge_configs(DEFAULT_CONFIG, file_config)
            logger.info(f"Loaded configuration from {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path like 'claim_detection.statistical.enabled'
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path like 'claim_detection.statistical.enabled'
            value: Value to set
        """
        keys = key_path.split('.')
        config = self.config
        
        # Navigate to parent dict
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the final value
        config[keys[-1]] = value
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def save_config(self, config_path: Path) -> None:
        """Save current configuration to YAML file."""
        if not YAML_AVAILABLE:
            logger.error("PyYAML not available, cannot save config file")
            return
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            logger.info(f"Saved configuration to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self.config.copy()
