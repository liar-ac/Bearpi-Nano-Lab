"""
AI接口输入校验测试:畸形请求体必须返回400而不是500,且不触发上游AI调用。
"""
import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.models import UserRoleProfile


class AiInputValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username="ai-admin", password="x")
        UserRoleProfile.objects.create(user=self.admin, role=UserRoleProfile.Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def test_query_question_none_returns_400(self):
        response = self.client.post("/api/v1/ai/query", {"question": None}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_query_question_non_string_returns_400(self):
        response = self.client.post("/api/v1/ai/query", {"question": 123}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_query_array_body_returns_400(self):
        response = self.client.post("/api/v1/ai/query", [1, 2, 3], format="json")
        self.assertEqual(response.status_code, 400)

    def test_command_text_none_returns_400(self):
        response = self.client.post("/api/v1/ai/command", {"text": None}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_chat_type_skewed_context_returns_400(self):
        response = self.client.post(
            "/api/v1/ai/chat",
            {"feature": "alarm_diagnosis", "context": {"alarm": "x"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class AiCommandEnumGuardTests(TestCase):
    """LLM返回枚举外的actuator/mode时必须回退为detected=False,不得透传给客户端。"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username="ai-enum-admin", password="x")
        UserRoleProfile.objects.create(user=self.admin, role=UserRoleProfile.Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def _mock_ai_reply(self, payload):
        return mock.patch(
            "apps.ai.views.call_ai_api",
            return_value=Response({"reply": json.dumps(payload, ensure_ascii=False)}),
        )

    def test_out_of_set_actuator_returns_not_detected(self):
        payload = {
            "detected": True, "device_sn": "BEARPI-NANO-A001",
            "actuator": "buzzer", "mode": "on", "confidence": 0.9, "explanation": "x",
        }
        with self._mock_ai_reply(payload) as mocked:
            response = self.client.post("/api/v1/ai/command", {"text": "把A001的蜂鸣器打开"}, format="json")
        self.assertTrue(mocked.called)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["detected"])

    def test_unknown_mode_returns_not_detected(self):
        payload = {
            "detected": True, "device_sn": "BEARPI-NANO-A001",
            "actuator": "light", "mode": "unknown", "confidence": 0.9, "explanation": "x",
        }
        with self._mock_ai_reply(payload) as mocked:
            response = self.client.post("/api/v1/ai/command", {"text": "调一下A001的补光"}, format="json")
        self.assertTrue(mocked.called)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["detected"])
