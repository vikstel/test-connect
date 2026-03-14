import asyncio
import concurrent.futures
from telegram import Bot
from telegram.error import TelegramError
from .base import BasePlatform


def _run(coro):
    """Run async coroutine safely even inside a running event loop (FastAPI)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


class TelegramPoster(BasePlatform):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def _bot(self):
        return Bot(token=self.bot_token)

    def test_connection(self) -> dict:
        try:
            info = _run(self._bot().get_me())
            return {"ok": True, "message": f"Бот @{info.username} подключён"}
        except TelegramError as e:
            return {"ok": False, "message": str(e)}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            bot = self._bot()
            if media_path and media_type == "photo":
                with open(media_path, "rb") as f:
                    msg = _run(bot.send_photo(self.chat_id, photo=f, caption=text))
            elif media_path and media_type == "video":
                with open(media_path, "rb") as f:
                    msg = _run(bot.send_video(self.chat_id, video=f, caption=text))
            else:
                msg = _run(bot.send_message(self.chat_id, text=text))
            return {"ok": True, "post_id": str(msg.message_id)}
        except TelegramError as e:
            return {"ok": False, "message": str(e)}
        except Exception as e:
            return {"ok": False, "message": str(e)}
