from django.contrib import admin
from .models import Patient, Token, NotificationLog, UserProfile

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'mobile_number', 'created_at')
    search_fields = ('full_name', 'email', 'mobile_number')
    list_filter = ('created_at',)

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'patient', 'department', 'doctor_name', 'status', 'created_at', 'called_at', 'completed_at')
    search_fields = ('token_number', 'patient__full_name', 'doctor_name', 'department')
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

