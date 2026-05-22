from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserRoleProfile


class AuditLogPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username="admin-user", password="x")
        self.viewer = User.objects.create_user(username="viewer-user", password="x")
        UserRoleProfile.objects.create(user=self.admin, role=UserRoleProfile.Role.ADMIN)
        UserRoleProfile.objects.create(user=self.viewer, role=UserRoleProfile.Role.VIEWER)

    def test_admin_can_view_audit_logs(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/audit-logs")
        self.assertEqual(response.status_code, 200)

    def test_viewer_cannot_view_audit_logs(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get("/api/v1/audit-logs")
        self.assertEqual(response.status_code, 403)
