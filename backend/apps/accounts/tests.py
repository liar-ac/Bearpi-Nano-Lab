from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserRoleProfile


class RegisterValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # 注册接口有 auth_register 限流，清理缓存避免跨用例触发 429
        cache.clear()

    def register(self, username, password):
        return self.client.post(
            "/api/v1/auth/register",
            {"username": username, "password": password},
            format="json",
        )

    def test_register_rejects_username_with_space(self):
        response = self.register("bad user", "Vt9#kPz7Qw")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="bad user").exists())

    def test_register_rejects_password_identical_to_username(self):
        response = self.register("sampleuser2026", "sampleuser2026")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="sampleuser2026").exists())

    def test_register_valid_user_returns_201(self):
        response = self.register("newlabuser", "Vt9#kPz7Qw")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="newlabuser")
        self.assertEqual(user.role_profile.role, UserRoleProfile.Role.VIEWER)
