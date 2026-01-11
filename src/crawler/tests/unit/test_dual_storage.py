"""
Unit tests for DualStorageDescriptor.
"""

import pytest
from decimal import Decimal
from package.models.fields import DualStorageDescriptor
from package.utils import converter


class MockModel:
    """Mock model for testing descriptors."""
    
    def __init__(self):
        self.priceStr = None
        self.price = None
        self.senyuMensekiStr = None
        self.senyuMenseki = None
    
    # Define descriptors
    price_dual = DualStorageDescriptor('priceStr', 'price', converter.parse_price)
    senyuMenseki_dual = DualStorageDescriptor('senyuMensekiStr', 'senyuMenseki', converter.parse_menseki)


class TestDualStorageDescriptor:
    """Test cases for DualStorageDescriptor."""
    
    def test_set_price_string(self):
        """Test setting price with string value."""
        model = MockModel()
        model.price_dual = "5,480万円"
        
        assert model.priceStr == "5,480万円"
        assert model.price == 54800000
    
    def test_set_menseki_string(self):
        """Test setting menseki with string value."""
        model = MockModel()
        model.senyuMenseki_dual = "81.65㎡"
        
        assert model.senyuMensekiStr == "81.65㎡"
        assert model.senyuMenseki == Decimal("81.65")
    
    def test_set_none_value(self):
        """Test setting None value."""
        model = MockModel()
        model.price_dual = None
        
        assert model.priceStr is None
        assert model.price is None
    
    def test_set_empty_string(self):
        """Test setting empty string."""
        model = MockModel()
        model.price_dual = ""
        
        assert model.priceStr == ""
        assert model.price is None
    
    def test_get_value(self):
        """Test getting value returns string field."""
        model = MockModel()
        model.price_dual = "5,480万円"
        
        # Getting the descriptor should return the string value
        assert model.price_dual == "5,480万円"
    
    def test_multiple_assignments(self):
        """Test multiple assignments to the same descriptor."""
        model = MockModel()
        
        model.price_dual = "3,000万円"
        assert model.price == 30000000
        
        model.price_dual = "5,000万円"
        assert model.price == 50000000
        
        model.price_dual = None
        assert model.price is None
