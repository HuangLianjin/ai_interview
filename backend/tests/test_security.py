"""安全模块单元测试：限流器。"""
import unittest

from app.services.security import InMemoryRateLimiter


class RateLimiterTest(unittest.TestCase):
    def test_allows_until_limit(self):
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            self.assertTrue(limiter.allow("k", 5, 60))
        self.assertFalse(limiter.allow("k", 5, 60))

    def test_reset(self):
        limiter = InMemoryRateLimiter()
        limiter.allow("k", 1, 60)
        self.assertFalse(limiter.allow("k", 1, 60))
        limiter.reset("k")
        self.assertTrue(limiter.allow("k", 1, 60))


if __name__ == "__main__":
    unittest.main()