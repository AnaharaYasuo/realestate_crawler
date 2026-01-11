
class ApiRegistry:
    _registry = {}

    @classmethod
    def register(cls, key: str, class_ref):
        """
        Register a class reference with a specific API key (path suffix).
        """
        cls._registry[key] = class_ref

    @classmethod
    def get(cls, key: str):
        """
        Retrieve a class reference by API key.
        Returns None if not found.
        """
        return cls._registry.get(key)
