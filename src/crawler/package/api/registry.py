
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
        if not key:
            return None
        res = cls._registry.get(key)
        if res is not None:
            return res

        # Normalization fallback for legacy GCP endpoints (e.g. /nomura_mansion_region -> /api/nomura/mansion/region)
        if not key.startswith("/api/"):
            normalized = "/api/" + key.lstrip("/").replace("_", "/")
            res = cls._registry.get(normalized)
            if res is not None:
                return res

        return None
