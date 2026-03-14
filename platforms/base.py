from abc import ABC, abstractmethod


class BasePlatform(ABC):
    @abstractmethod
    def test_connection(self) -> dict:
        """Returns {"ok": True/False, "message": "..."}"""
        ...

    @abstractmethod
    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        """Returns {"ok": True/False, "post_id": "...", "message": "..."}"""
        ...
