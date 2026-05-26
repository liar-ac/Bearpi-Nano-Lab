from django.urls import path

from apps.ai.views import AiChatView, AiHealthView, AiQueryView

urlpatterns = [
    path("ai/health", AiHealthView.as_view(), name="ai-health"),
    path("ai/chat", AiChatView.as_view(), name="ai-chat"),
    path("ai/query", AiQueryView.as_view(), name="ai-query"),
]
