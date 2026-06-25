from django.contrib import admin
from .models import QueueToken, NotificationLog, UserProfile

@admin.register(QueueToken)
class QueueTokenAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'full_name', 'mobile_number', 'email', 'department', 'doctor_name', 'status', 'created_at', 'called_at')
    search_fields = ('token_number', 'full_name', 'mobile_number', 'email', 'doctor_name', 'department')
    list_filter = ('status', 'department', 'created_at')

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'notification_type', 'sent_at')
    search_fields = ('token__token_number', 'notification_type')
    list_filter = ('notification_type', 'sent_at')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'role', 'department', 'license_number')
    search_fields = ('user__username', 'role', 'department')
    list_filter = ('role', 'department')
