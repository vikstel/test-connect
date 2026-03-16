import tweepy
from .base import BasePlatform


class TwitterPoster(BasePlatform):
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str, **kwargs):
        # Клиент v2 API для твитов
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        # API v1.1 для загрузки медиа (v2 не поддерживает media upload)
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        self.api_v1 = tweepy.API(auth)

    def test_connection(self) -> dict:
        try:
            me = self.client.get_me()
            return {"ok": True, "message": f"Twitter: @{me.data.username}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _upload_media(self, media_path: str, media_type: str) -> str | None:
        """Загружает медиафайл через v1.1 API, возвращает media_id."""
        if media_type == "photo":
            media = self.api_v1.media_upload(media_path)
        elif media_type == "video":
            # Видео загружаем через chunked upload (async)
            media = self.api_v1.chunked_upload(media_path, media_type="video/mp4", media_category="tweet_video")
            # Ждём обработки
            import time
            for _ in range(20):
                status = self.api_v1.get_media_upload_status(media.media_id)
                state = status.processing_info.get("state")
                if state == "succeeded":
                    break
                elif state == "failed":
                    raise Exception(f"Video processing failed: {status.processing_info}")
                time.sleep(status.processing_info.get("check_after_secs", 3))
        else:
            return None
        return str(media.media_id)

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            media_ids = None
            if media_path and media_type in ("photo", "video"):
                media_id = self._upload_media(media_path, media_type)
                if media_id:
                    media_ids = [media_id]

            tweet = self.client.create_tweet(text=text, media_ids=media_ids)
            return {"ok": True, "post_id": str(tweet.data["id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
