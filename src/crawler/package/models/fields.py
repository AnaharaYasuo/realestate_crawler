"""
Custom field descriptors for implementing Dual Storage Pattern.

This module provides descriptors that automatically manage both string and
numeric representations of data fields, preventing data inconsistencies.
"""

from typing import Callable, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DualStorageDescriptor:
    """
    Descriptor that automatically manages both string and numeric fields.
    
    When a value is set via this descriptor, it automatically:
    1. Stores the raw string value in the string field
    2. Converts and stores the numeric value in the numeric field
    
    This prevents data inconsistencies and simplifies parser code.
    
    Example:
        class MitsuiMansion(models.Model):
            priceStr = models.TextField()
            price = models.IntegerField()
            
            # Define descriptor
            price_dual = DualStorageDescriptor('priceStr', 'price', converter.parse_price)
        
        # Usage in parser
        item.price_dual = "5,480万円"  # Sets both priceStr and price automatically
    """
    
    def __init__(
        self,
        str_field: str,
        numeric_field: str,
        converter: Callable[[str], Any]
    ):
        """
        Initialize the descriptor.
        
        Args:
            str_field: Name of the string field (e.g., 'priceStr')
            numeric_field: Name of the numeric field (e.g., 'price')
            converter: Function to convert string to numeric value
        """
        self.str_field = str_field
        self.numeric_field = numeric_field
        self.converter = converter
        self.name = None
    
    def __set_name__(self, owner, name):
        """Called when the descriptor is assigned to a class attribute."""
        self.name = name
    
    def __get__(self, obj, objtype=None):
        """
        Get the string value.
        
        Returns the string field value when accessed.
        """
        if obj is None:
            return self
        return getattr(obj, self.str_field, None)
    
    def __set__(self, obj, value):
        """
        Set both string and numeric values.
        
        Args:
            obj: The model instance
            value: The raw string value to set
        """
        # Set the string field with the raw value
        setattr(obj, self.str_field, value)
        
        # Convert and set the numeric field
        if value is None or value == '':
            setattr(obj, self.numeric_field, None)
        else:
            try:
                numeric_value = self.converter(value)
                setattr(obj, self.numeric_field, numeric_value)
            except Exception as e:
                logger.warning(
                    f"Failed to convert '{value}' using {self.converter.__name__}: {e}"
                )
                setattr(obj, self.numeric_field, None)


class ReadOnlyDualStorageDescriptor:
    """
    Read-only version of DualStorageDescriptor.
    
    This descriptor only provides read access to the string field.
    Useful for computed or derived fields.
    """
    
    def __init__(self, str_field: str):
        """
        Initialize the read-only descriptor.
        
        Args:
            str_field: Name of the string field to read from
        """
        self.str_field = str_field
        self.name = None
    
    def __set_name__(self, owner, name):
        """Called when the descriptor is assigned to a class attribute."""
        self.name = name
    
    def __get__(self, obj, objtype=None):
        """Get the string value."""
        if obj is None:
            return self
        return getattr(obj, self.str_field, None)
    
    def __set__(self, obj, value):
        """Prevent setting the value."""
        raise AttributeError(
            f"{self.name} is read-only. Set {self.str_field} directly instead."
        )
