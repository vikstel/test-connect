import tweepy
from .base import BasePlatform


class TwitterPoster(BasePlatform):
    def __init__(self, access_token: str, **kwargs):
        # OAuth 2.0 user context — только один токен нужен пользователю
        self.client = tweepy.Client(access_token=access_token)

    def test_connection(self) -> dict:
        try:
            me = self.client.get_me()
            return {"ok": True, "message": f"Twitter: @{me.data.username}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            # Media upload через v1.1 API требует OAuth 1.0a — не поддерживается в OAuth 2.0 flow
            # Публикуем текст (изображения требуют переход на OAuth 1.0a / Enterprise)
            tweet = self.client.create_tweet(text=text)
            return {"ok": True, "post_id": str(tweet.data["id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
