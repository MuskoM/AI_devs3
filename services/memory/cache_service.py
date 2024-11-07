import pathlib as p
from base64 import urlsafe_b64encode

class SimpleHTTPCacheService:
    CACHE_DIR = './cache'
    def __init__(self) -> None:
        self.cache_dir_path = p.Path(self.CACHE_DIR)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        if not self.cache_dir_path.exists():
            self.cache_dir_path.mkdir()

    def get(self, url: str) -> str:
        hash = urlsafe_b64encode(url.encode())
        cached_file = self.cache_dir_path.joinpath(hash.decode())
        if cached_file.exists():
            with open(cached_file, 'r') as file:
                return file.read()
        else:
            return ''

    def save(self, url: str, data: str):
        hash = urlsafe_b64encode(url.encode())
        cached_file = self.cache_dir_path.joinpath(hash.decode())
        with open(cached_file, 'w') as file:
            file.write(data)

