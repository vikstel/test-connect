import tweepy
from .base import BasePlatform


class TwitterPoster(BasePlatform):
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )

    def test_connection(self) -> dict:
        try:
            me = self.client.get_me()
            return {"ok": True, "message": f"Twitter: @{me.data.username}"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            tweet = self.client.create_tweet(text=text)
            return {"ok": True, "post_id": str(tweet.data["id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
