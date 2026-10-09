import os
import unittest
from unittest.mock import patch

from package.api.adaptive_concurrency import AdaptiveConcurrencyController


class TestAdaptiveConcurrencySiteCaps(unittest.TestCase):
    def setUp(self):
        # Clear env vars
        os.environ.pop("CLOUD_DETAIL_CONCURRENCY", None)
        os.environ.pop("CONTAINER_ACTIVE_JOBS", None)

    def test_site_concurrency_caps(self):
        # When active_jobs is 1, normal concurrency is 15
        base_concurrency = AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=1)
        self.assertEqual(base_concurrency, 15)

        # nomura and mitsui should be capped at 2
        effective_nomura = AdaptiveConcurrencyController.get_effective_concurrency(company="nomura", active_jobs=1)
        self.assertEqual(effective_nomura, 2)

        effective_mitsui = AdaptiveConcurrencyController.get_effective_concurrency(company="mitsui", active_jobs=1)
        self.assertEqual(effective_mitsui, 2)

        # Uncapped site (e.g. tokyu) should remain 15
        effective_tokyu = AdaptiveConcurrencyController.get_effective_concurrency(company="tokyu", active_jobs=1)
        self.assertEqual(effective_tokyu, 15)

    def test_site_concurrency_caps_under_throttling(self):
        with patch.object(AdaptiveConcurrencyController, "is_throttled", return_value=True):
            # When throttled, normal is 2. Caps are also 2, so min(2, 2) is 2.
            self.assertEqual(AdaptiveConcurrencyController.get_effective_concurrency(company="nomura"), 2)
            self.assertEqual(AdaptiveConcurrencyController.get_effective_concurrency(company="tokyu"), 2)


if __name__ == "__main__":
    unittest.main()
