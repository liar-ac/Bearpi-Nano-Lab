from django.urls import path

from apps.ai.views import AiChatView, AiCommandParseView, AiHealthView, AiPingView, AiQueryView

urlpatterns = [
    path("ai/health", AiHealthView.as_view(), name="ai-health"),
    path("ai/ping", AiPingView.as_view(), name="ai-ping"),
    path("ai/chat", AiChatView.as_view(), name="ai-chat"),
    path("ai/query", AiQueryView.as_view(), name="ai-query"),
    path("ai/command", AiCommandParseView.as_view(), name="ai-command"),
]
