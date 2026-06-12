"""
AI接口输入校验测试:畸形请求体必须返回400而不是500,且不触发上游AI调用。
"""
from django.contrib.auth.models import User
from django.test import TestCase
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
