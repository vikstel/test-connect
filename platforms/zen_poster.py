import json
from pathlib import Path
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from .base import BasePlatform

RSS_FILE = Path("static/rss.xml")
ZEN_POSTS_FILE = Path("zen_posts.json")


class ZenPoster(BasePlatform):
    def __init__(self, feed_title: str, author_name: str, base_url: str = "http://localhost:8000"):
        self.feed_title = feed_title
        self.author_name = author_name
        self.base_url = base_url

    def _load_posts(self) -> list:
        if ZEN_POSTS_FILE.exists():
            return json.loads(ZEN_POSTS_FILE.read_text())
        return []

    def _save_posts(self, posts: list):
        ZEN_POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2))

    def _regenerate_rss(self, posts: list):
        fg = FeedGenerator()
        fg.id(f"{self.base_url}/static/rss.xml")
        fg.title(self.feed_title)
        fg.description(self.feed_title)  # обязательное поле RSS 2.0
        fg.author({"name": self.author_name})
        fg.link(href=f"{self.base_url}/static/rss.xml", rel="self")
        for post in posts[-50:]:
            fe = fg.add_entry()
            fe.id(post["id"])
            fe.title(post["title"])
            fe.content(post["content"], type="html")
            # feedgen принимает строку ISO 8601 или datetime объект
            pub = post["published"]
            if isinstance(pub, str):
                pub = datetime.fromisoformat(pub)
            fe.published(pub)
        fg.rss_file(str(RSS_FILE))

    def test_connection(self) -> dict:
        return {"ok": True, "message": f"RSS готов: {self.base_url}/static/rss.xml"}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            posts = self._load_posts()
            post_id = f"post-{len(posts)+1}-{int(datetime.now().timestamp())}"
            title = text[:80] + ("..." if len(text) > 80 else "")
            posts.append({
                "id": f"{self.base_url}/{post_id}",
                "title": title,
                "content": f"<p>{text}</p>",
                # ISO 8601 с UTC timezone для feedgen
                "published": datetime.now(timezone.utc).isoformat()
            })
            self._save_posts(posts)
            self._regenerate_rss(posts)
            return {"ok": True, "post_id": post_id, "message": "Добавлено в RSS"}
        except Exception as e:
            return {"ok": False, "message": str(e)}
