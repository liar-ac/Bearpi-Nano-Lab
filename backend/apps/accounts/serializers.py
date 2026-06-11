from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRoleProfile


LEGACY_ROLE_MAP = {
    "admin": UserRoleProfile.Role.ADMIN,
    "exp": UserRoleProfile.Role.EXPERIMENTER,
    "lab": UserRoleProfile.Role.EXPERIMENTER,
    "viewer": UserRoleProfile.Role.VIEWER,
}


def resolve_role(user):
    if user.is_superuser or user.is_staff:
        return UserRoleProfile.Role.ADMIN
    profile = getattr(user, "role_profile", None)
    if profile is not None:
        return profile.role
    return LEGACY_ROLE_MAP.get(user.username, UserRoleProfile.Role.VIEWER)


def build_auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "user": {
            "id": user.id,
            "name": user.get_full_name() or user.username,
            "role": resolve_role(user),
            "team": "小熊派 Nano 项目组",
        },
    }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("账号或密码错误")
        if not user.is_active:
            raise serializers.ValidationError("账号已被禁用")
        return build_auth_payload(user)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    password = serializers.CharField(write_only=True, min_length=6, max_length=128)
    name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("账号不能为空")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("该账号已存在")
        return value

    def validate_name(self, value):
        return value.strip() if value else ""

    def create(self, validated_data):
        username = validated_data["username"]
        password = validated_data["password"]
        name = validated_data.get("name", "").strip()
        try:
            validate_password(password)
        except Exception as exc:
            error_messages = exc.messages if hasattr(exc, 'messages') else [str(exc)]
            raise serializers.ValidationError({"password": error_messages})
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, password=password)
                if name:
                    user.first_name = name
                    user.save(update_fields=["first_name"])
                UserRoleProfile.objects.create(user=user, role=UserRoleProfile.Role.VIEWER)
                return user
        except IntegrityError:
            raise serializers.ValidationError({"username": "该账号已存在"})


class AccountUserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source="is_active")
    createdAt = serializers.DateTimeField(source="date_joined")

    class Meta:
        model = User
        fields = ["id", "username", "name", "role", "isActive", "createdAt"]

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_role(self, obj):
        return resolve_role(obj)


class AccountRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[
            (UserRoleProfile.Role.ADMIN, "管理员"),
            (UserRoleProfile.Role.EXPERIMENTER, "实验员"),
            (UserRoleProfile.Role.VIEWER, "只读"),
        ]
    )
