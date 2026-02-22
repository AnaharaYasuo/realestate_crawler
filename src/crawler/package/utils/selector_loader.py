"""
Selector loader utility for loading CSS selectors from YAML configuration files.

This module provides a centralized way to manage CSS selectors used in parsers,
making it easy to update selectors when website structures change without
modifying code.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SelectorLoader:
    """
    Utility class for loading and caching CSS selectors from YAML files.
    
    Selectors are loaded from config/selectors/{company}.yaml files and
    cached in memory for performance.
    
    Example:
        # Load selectors for Mitsui mansion
        selectors = SelectorLoader.load('mitsui', 'mansion')
        
        # Use selectors in parser
        title_el = response.select_one(selectors['title'])
        price_el = response.select_one(selectors['price'])
    """
    
    _cache: Dict[str, Dict[str, Any]] = {}
    _config_dir: Optional[Path] = None
    
    @classmethod
    def set_config_dir(cls, config_dir: Path):
        """
        Set the configuration directory path.
        
        Args:
            config_dir: Path to the config/selectors directory
        """
        cls._config_dir = config_dir
    

    @classmethod
    def get_config_dir(cls) -> Path:
        """
        Get the configuration directory path.
        
        Returns:
            Path to the config/selectors directory
        """
        if cls._config_dir is None:
            # Default: config/selectors relative to project root
            # Assuming this file is in src/crawler/package/utils/
            current_file = Path(__file__).resolve()
            
            # Try to find project root by looking for 'src' in parents
            root = current_file.parent
            while root.name != 'src' and root.parent != root:
                root = root.parent
            
            if root.name == 'src':
                # We found src, parent is project root
                project_root = root.parent
            else:
                # Fallback: assume standard depth if src not found in path matching
                # utils -> package -> crawler -> src -> root (4 levels up from package/utils)
                # current_file -> utils -> package -> crawler -> src -> root
                project_root = current_file.parent.parent.parent.parent.parent

            # Candidate paths
            candidate_paths = [
                project_root / "config" / "selectors",
                Path("/app/config/selectors"),  # Docker default
                Path("C:/Users/weare/Documents/realestate_crawler/config/selectors") # Windows absolute fallback
            ]

            for path in candidate_paths:
                if path.exists():
                    cls._config_dir = path
                    break
            
            if cls._config_dir is None:
                # Fallback to calculated path even if not exists, for error reporting
                cls._config_dir = project_root / "config" / "selectors"
                logger.warning(f"Config directory not found. defaulting to {cls._config_dir}")
        
        return cls._config_dir
    
    @classmethod
    def load(cls, company: str, property_type: str) -> Dict[str, Any]:
        """
        Load selectors for a specific company and property type.
        
        Args:
            company: Company name (e.g., 'mitsui', 'sumifu')
            property_type: Property type (e.g., 'mansion', 'kodate', 'tochi')
        
        Returns:
            Dictionary containing selectors for the specified company and type
        
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            KeyError: If the property type is not defined in the config
            yaml.YAMLError: If the YAML file is malformed
        """
        cache_key = f"{company}_{property_type}"
        
        # Return cached selectors if available
        if cache_key in cls._cache:
            logger.debug(f"Using cached selectors for {cache_key}")
            return cls._cache[cache_key]
        
        # Load selectors from YAML file
        config_dir = cls.get_config_dir()
        config_path = config_dir / f"{company}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Selector configuration file not found: {config_path}"
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file {config_path}: {e}")
            raise
        
        if property_type not in config:
            raise KeyError(
                f"Property type '{property_type}' not found in {config_path}. "
                f"Available types: {list(config.keys())}"
            )
        
        # Cache and return selectors
        selectors = config[property_type]
        cls._cache[cache_key] = selectors
        logger.info(f"Loaded selectors for {cache_key} from {config_path}")
        
        return selectors
    
    @classmethod
    def clear_cache(cls):
        """Clear the selector cache. Useful for testing or reloading configs."""
        cls._cache.clear()
        logger.info("Selector cache cleared")
    
    @classmethod
    def reload(cls, company: str, property_type: str) -> Dict[str, Any]:
        """
        Reload selectors for a specific company and property type.
        
        This clears the cache for the specified selectors and reloads them.
        
        Args:
            company: Company name
            property_type: Property type
        
        Returns:
            Dictionary containing reloaded selectors
        """
        cache_key = f"{company}_{property_type}"
        if cache_key in cls._cache:
            del cls._cache[cache_key]
            logger.info(f"Cleared cache for {cache_key}")
        
        return cls.load(company, property_type)
