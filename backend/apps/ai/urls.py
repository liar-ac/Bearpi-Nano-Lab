from django.urls import path

from apps.ai.views import AiChatView, AiQueryView

urlpatterns = [
    path("ai/chat", AiChatView.as_view(), name="ai-chat"),
    path("ai/query", AiQueryView.as_view(), name="ai-query"),
]
