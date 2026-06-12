import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


class RealtimeConsumer(AsyncJsonWebsocketConsumer):
    """实时通道：所有已登录用户加入同一个全局 group，便于单实验室广播。

    未来如需做多租户/按实验室隔离，可改成读取用户的 lab_id 并加入 ``realtime:<lab_id>``，
    同时让 ``persist_and_publish`` 与告警推送按 lab_id 分流。当前后端是单实验室部署，
    全局 group + JWT 鉴权已经足够。
    """

    @property
    def group_name(self) -> str:
        return getattr(settings, "REALTIME_GROUP_NAME", "realtime")

    async def connect(self):
        token = self.extract_token()
        if not token:
            await self.accept()
            await self.close(code=4401)
            return

        user = await self.resolve_user(token)
        if user is None:
            await self.accept()
            await self.close(code=4401)
            return

        self.user = user
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def sensor_point(self, event):
        await self.send_json({
            "type": "sensor.point",
            "payload": event["payload"],
        })

    async def alarm_event(self, event):
        await self.send_json({
            "type": "alarm.event",
            "payload": event["payload"],
        })

    def extract_token(self):
        query = self.scope.get("query_string", b"").decode("utf-8")
        token = parse_qs(query).get("token", [""])[0]
        return token.strip()

    @database_sync_to_async
    def resolve_user(self, token):
        try:
            payload = AccessToken(token)
        except TokenError as exc:
            logger.warning("WebSocket auth failed (token invalid or expired): %s", exc)
            return None
        # Explicit expiry check: AccessToken validates by default, but guard
        # against configurations where VERIFY_EXPIRATION might be disabled.
        try:
            exp_timestamp = payload.get("exp")
            if exp_timestamp is not None and exp_timestamp < timezone.now().timestamp():
                logger.warning("WebSocket rejected: token expired at %s", exp_timestamp)
                return None
        except Exception:
            pass
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return get_user_model().objects.filter(pk=user_id, is_active=True).first()
