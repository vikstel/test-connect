import vk_api
from .base import BasePlatform


class VKPoster(BasePlatform):
    def __init__(self, access_token: str, target_id: str, app_id: str = None, client_secret: str = None):
        self.session = vk_api.VkApi(token=access_token)
        self.vk = self.session.get_api()
        self.owner_id = int(target_id)

    def test_connection(self) -> dict:
        try:
            info = self.vk.users.get()
            if info:
                user = info[0]
                return {"ok": True, "message": f"Подключён как {user['first_name']} {user['last_name']}"}
            # Group token — check via groups API
            group_info = self.vk.groups.getById(group_id=abs(self.owner_id))
            group = group_info[0]
            return {"ok": True, "message": f"Подключён как группа «{group['name']}»"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def post(self, text: str, media_path: str = None, media_type: str = None) -> dict:
        try:
            attachments = []
            if media_path and media_type == "photo":
                upload = vk_api.VkUpload(self.session)
                photo = upload.photo_wall(media_path, group_id=abs(self.owner_id))
                p = photo[0]
                attachments.append(f"photo{p['owner_id']}_{p['id']}")
            result = self.vk.wall.post(
                owner_id=self.owner_id,
                message=text,
                attachments=",".join(attachments)
            )
            return {"ok": True, "post_id": str(result["post_id"])}
        except Exception as e:
            return {"ok": False, "message": str(e)}
