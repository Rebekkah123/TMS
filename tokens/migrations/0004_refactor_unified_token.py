from django.db import migrations, models


def migrate_tokens_forward(apps, schema_editor):
    """
    Copy data from old Token + Patient tables into the new QueueToken table.
    Skips COMPLETED tokens since the new system does not retain completed records.
    """
    Token = apps.get_model('tokens', 'Token')
    QueueToken = apps.get_model('tokens', 'QueueToken')
    NotificationLog = apps.get_model('tokens', 'NotificationLog')

    token_id_map = {}  # old Token.id -> new QueueToken.id

    for old_token in Token.objects.select_related('patient').exclude(status='COMPLETED'):
        new_token = QueueToken.objects.create(
            token_number=old_token.token_number,
            department=old_token.department,
            doctor_name=old_token.doctor_name,
            status=old_token.status,
            created_at=old_token.created_at,
            called_at=old_token.called_at,
            full_name=old_token.patient.full_name,
            email=old_token.patient.email,
            mobile_number=old_token.patient.mobile_number,
        )
        token_id_map[old_token.id] = new_token.id

    # Re-point NotificationLog rows to the new QueueToken rows
    for log in NotificationLog.objects.filter(token_id__in=token_id_map.keys()):
        log.token_id = token_id_map[log.token_id]
        log.save()


def migrate_tokens_backward(apps, schema_editor):
    """
    Reverse: clear QueueToken data (best-effort only; original Patient rows are gone).
    """
    QueueToken = apps.get_model('tokens', 'QueueToken')
    QueueToken.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tokens', '0003_alter_token_token_number'),
    ]

    operations = [
        # 1. Create the new unified QueueToken table
        migrations.CreateModel(
            name='QueueToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_number', models.PositiveIntegerField()),
                ('department', models.CharField(
                    choices=[
                        ('General Medicine', 'General Medicine'),
                        ('Cardiology', 'Cardiology'),
                        ('Neurology', 'Neurology'),
                        ('Pediatrics', 'Pediatrics'),
                        ('Orthopedics', 'Orthopedics'),
                        ('Dermatology', 'Dermatology'),
                        ('Emergency', 'Emergency'),
                        ('Surgery', 'Surgery'),
                    ],
                    max_length=50,
                )),
                ('doctor_name', models.CharField(blank=True, max_length=255, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('WAITING', 'Waiting'),
                        ('NEAR_TURN', 'Near Turn'),
                        ('CALLED', 'Called'),
                        ('SKIPPED', 'Skipped'),
                    ],
                    default='WAITING',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('called_at', models.DateTimeField(blank=True, null=True)),
                ('full_name', models.CharField(max_length=255)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('mobile_number', models.CharField(max_length=20)),
            ],
        ),

        # 2. Migrate existing active data into QueueToken
        migrations.RunPython(migrate_tokens_forward, migrate_tokens_backward),

        # 3. Swap NotificationLog FK from Token -> QueueToken
        migrations.AlterField(
            model_name='notificationlog',
            name='token',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name='notifications',
                to='tokens.queuetoken',
            ),
        ),

        # 4. Drop the old Token and Patient tables
        migrations.DeleteModel(name='Token'),
        migrations.DeleteModel(name='Patient'),
    ]
