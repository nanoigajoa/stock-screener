import os
from diskcache import Cache

# 데이터 저장을 위한 캐시 디렉토리 설정
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")

# 캐시 인스턴스 초기화 (shards=8은 병렬 접근 성능 향상용)
# diskcache는 프로세스/스레드 안전함
cache = Cache(CACHE_DIR)

def get_cache():
    return cache

def clear_cache():
    cache.clear()
