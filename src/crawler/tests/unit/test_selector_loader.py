"""
Unit tests for SelectorLoader.

Note: These tests are simplified to avoid file system dependencies in Docker.
Full integration tests should be run separately.
"""

import pytest
from pathlib import Path
from package.utils.selector_loader import SelectorLoader


class TestSelectorLoader:
    """Test cases for SelectorLoader."""
    
    def setup_method(self):
        """Clear cache before each test."""
        SelectorLoader.clear_cache()
    
    def test_cache_clear(self):
        """Test that cache can be cleared."""
        # Add something to cache manually
        SelectorLoader._cache['test_key'] = {'test': 'value'}
        
        # Clear cache
        SelectorLoader.clear_cache()
        
        # Cache should be empty
        assert len(SelectorLoader._cache) == 0
    
    def test_get_config_dir(self):
        """Test that config dir can be retrieved."""
        config_dir = SelectorLoader.get_config_dir()
        
        # Should return a Path object
        assert isinstance(config_dir, Path)
        
        # Should end with config/selectors
        assert config_dir.name == 'selectors'
        assert config_dir.parent.name == 'config'
    
    def test_set_config_dir(self):
        """Test that config dir can be set."""
        test_path = Path('/test/config/selectors')
        SelectorLoader.set_config_dir(test_path)
        
        # Should return the set path
        assert SelectorLoader.get_config_dir() == test_path
        
        # Reset to default
        SelectorLoader._config_dir = None
