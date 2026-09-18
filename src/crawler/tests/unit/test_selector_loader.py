"""
Unit tests for SelectorLoader.

Note: These tests are simplified to avoid file system dependencies in Docker.
Full integration tests should be run separately.
"""

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

    def test_real_selectors_load(self):
        """Test that actual configuration files exist and can be loaded."""
        config_dir = SelectorLoader.get_config_dir()
        assert config_dir.exists(), f"Config directory does not exist: {config_dir}"

        # Test loading selectors for key companies
        for company in ['mitsui', 'sumifu', 'daikyo', 'tokyu']:
            selectors = SelectorLoader.load(company, 'mansion')
            assert isinstance(selectors, dict)
            assert len(selectors) > 0

    def test_all_yaml_selectors_valid(self):
        """Verify all selector YAML files in config/selectors are valid YAML."""
        import yaml
        config_dir = SelectorLoader.get_config_dir()
        yaml_files = list(config_dir.glob("*.yaml"))
        assert len(yaml_files) >= 20, f"Expected at least 20 yaml selector files, found {len(yaml_files)}"

        for yf in yaml_files:
            with open(yf, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                assert isinstance(data, dict), f"{yf.name} should contain a YAML mapping"
                assert len(data) > 0, f"{yf.name} should not be empty"
