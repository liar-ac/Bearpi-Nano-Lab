from django.urls import path
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import AccountUserRoleView, AccountUsersView, LoginView, RegisterView


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"


urlpatterns = [
    path("login", LoginView.as_view(), name="login"),
    path("register", RegisterView.as_view(), name="register"),
    path("refresh", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
    path("users", AccountUsersView.as_view(), name="account-users"),
    path("users/<int:user_id>/role", AccountUserRoleView.as_view(), name="account-user-role"),
]
