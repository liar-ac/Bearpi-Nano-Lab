from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import UserRoleProfile
from apps.accounts.serializers import (
    AccountRoleUpdateSerializer,
    AccountUserSerializer,
    LoginSerializer,
    RegisterSerializer,
    build_auth_payload,
    resolve_role,
)
from apps.audit.models import AuditLog
from apps.audit.services import record_audit


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record_audit(
            request,
            AuditLog.Action.LOGIN,
            serializer.validated_data["user"]["name"],
            "用户登录控制台",
            {"role": serializer.validated_data["user"]["role"]},
            actor_name=serializer.validated_data["user"]["name"],
        )
        return Response(serializer.validated_data)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record_audit(request, AuditLog.Action.REGISTER, user.username, "新账号注册", {"role": "viewer"}, actor_name=user.username)
        return Response(build_auth_payload(user), status=201)


class AccountUsersView(APIView):
    def get(self, request):
        self.ensure_admin(request)
        users = User.objects.all().order_by("date_joined", "id")
        return Response(AccountUserSerializer(users, many=True).data)

    def ensure_admin(self, request):
        if resolve_role(request.user) != UserRoleProfile.Role.ADMIN:
            raise PermissionDenied("仅管理员可操作")


class AccountUserRoleView(APIView):
    def post(self, request, user_id):
        self.ensure_admin(request)
        serializer = AccountRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(User, pk=user_id)
        if user.is_superuser or user.is_staff:
            raise ValidationError({"role": "内置管理员账号角色不可修改"})
        next_role = serializer.validated_data["role"]
        if user.id == request.user.id and next_role != UserRoleProfile.Role.ADMIN:
            raise ValidationError({"role": "不能降低自己的管理员权限"})

        profile, _ = UserRoleProfile.objects.get_or_create(
            user=user,
            defaults={"role": UserRoleProfile.Role.VIEWER},
        )
        profile.role = next_role
        profile.save(update_fields=["role", "updated_at"])
        record_audit(
            request,
            AuditLog.Action.ROLE_UPDATE,
            user.username,
            f"用户角色调整为 {next_role}",
            {"userId": user.id, "role": next_role},
        )

        return Response(AccountUserSerializer(user).data)

    def ensure_admin(self, request):
        if resolve_role(request.user) != UserRoleProfile.Role.ADMIN:
            raise PermissionDenied("仅管理员可操作")
