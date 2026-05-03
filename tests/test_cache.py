import sys
import os
sys.path.append(os.getcwd())

from screener.cache_manager import cache
import time

def test_cache_persistence():
    key = "test_persistence_key"
    value = {"data": [1, 2, 3], "timestamp": time.time()}
    
    print(f"Setting cache: {key} -> {value}")
    cache.set(key, value, expire=10)
    
    cached_val = cache.get(key)
    print(f"Retrieved from cache: {cached_val}")
    
    assert cached_val == value
    print("Cache persistence test passed!")

if __name__ == "__main__":
    test_cache_persistence()
