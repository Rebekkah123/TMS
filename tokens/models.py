from django.db import models

class Department(models.TextChoices):
    GENERAL_MEDICINE = 'General Medicine', 'General Medicine'
    CARDIOLOGY = 'Cardiology', 'Cardiology'
    NEUROLOGY = 'Neurology', 'Neurology'
    PEDIATRICS = 'Pediatrics', 'Pediatrics'
    ORTHOPEDICS = 'Orthopedics', 'Orthopedics'
    DERMATOLOGY = 'Dermatology', 'Dermatology'
    EMERGENCY = 'Emergency', 'Emergency'
    SURGERY = 'Surgery', 'Surgery'

class TokenStatus(models.TextChoices):
    WAITING = 'WAITING', 'Waiting'
    NEAR_TURN = 'NEAR_TURN', 'Near Turn'
    CALLED = 'CALLED', 'Called'
    SKIPPED = 'SKIPPED', 'Skipped'

class QueueToken(models.Model):
    # Token details
    token_number = models.PositiveIntegerField()
    department = models.CharField(max_length=50, choices=Department.choices)
    doctor_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=TokenStatus.choices,
        default=TokenStatus.WAITING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)

    # Patient details (inlined — no separate Patient table)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    mobile_number = models.CharField(max_length=20)

    @property
    def token_prefix(self):
        if self.doctor_name:
            # Clean and generate prefix from doctor's name
            name = self.doctor_name.replace("Dr. ", "").replace("Dr ", "").strip()
            if name.lower() == "emergency":
                return "EMR"
            prefix = "".join(c for c in name if c.isalnum())
            if len(prefix) >= 3:
                return prefix[:3].upper()
            return prefix.upper().ljust(3, 'X')

        # Fallback to department prefixes if doctor_name is absent
        prefixes = {
            'General Medicine': 'GEN',
            'Cardiology': 'CARD',
            'Neurology': 'NEUR',
            'Pediatrics': 'PEDI',
            'Orthopedics': 'ORTHO',
            'Dermatology': 'DERM',
            'Emergency': 'EMER',
            'Surgery': 'SURG',
        }
        return prefixes.get(self.department, 'TKN')

    @property
    def formatted_token(self):
        return f"{self.token_prefix}-{self.token_number}"

    @property
    def wait_duration_minutes(self):
        from django.utils import timezone
        end_time = self.called_at or timezone.now()
        duration = end_time - self.created_at
        return int(duration.total_seconds() / 60)

    def __str__(self):
        return f"Token {self.token_number} - {self.full_name} ({self.department})"

class NotificationLog(models.Model):
    token = models.ForeignKey(QueueToken, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.notification_type} for Token {self.token.token_number} at {self.sent_at}"

from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('nurse', 'Nurse'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=50, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

class CompletedAppointment(models.Model):
    token_number = models.CharField(max_length=50)
    patient_name = models.CharField(max_length=255)
    doctor_name = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.token_number} - {self.patient_name}"

