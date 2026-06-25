from django.core.mail import send_mail
from .models import QueueToken, NotificationLog, TokenStatus

def send_registration_notification(token):
    """Send a confirmation email to the patient upon token registration."""
    recipient = token.email
    if not recipient:
        return

    print(f"Sending Registration Confirmation email to {recipient} for token {token.formatted_token}")
    try:
        send_mail(
            "Token Registration Confirmed - TMS Portal",
            (
                f"Dear {token.full_name},\n\n"
                f"You have been successfully registered at our clinic.\n\n"
                f"Your Token Number : {token.formatted_token}\n"
                f"Doctor            : {token.doctor_name}\n"
                f"Department        : {token.department}\n\n"
                f"Please keep this token number handy and arrive at the clinic on time.\n"
                f"You will receive further notifications as your turn approaches.\n\n"
                f"Thank you,\nTMS Portal"
            ),
            None,
            [recipient],
            fail_silently=False
        )
        print(f"Registration Confirmation email sent successfully to {recipient}")
        NotificationLog.objects.create(token=token, notification_type='Registration Confirmed')
    except Exception as e:
        print(f"Exception caught sending Registration Confirmation email to {recipient}:")
        import traceback
        traceback.print_exc()

def send_queue_started_notification(doctor_name):
    # Notify all waiting patients of this doctor with an email address
    waiting_tokens = QueueToken.objects.filter(
        status__in=[TokenStatus.WAITING, TokenStatus.NEAR_TURN],
        doctor_name=doctor_name,
        email__isnull=False
    ).exclude(email='')

    print(f"send_queue_started_notification called for doctor: {doctor_name}, waiting tokens: {[t.formatted_token for t in waiting_tokens]}")
    for token in waiting_tokens:
        recipient = token.email
        print(f"Sending Queue Started email to {recipient}")
        try:
            send_mail(
                "Queue Started - TMS Portal",
                (
                    f"Dear {token.full_name},\n\n"
                    f"The consultation queue has officially started today.\n"
                    f"Your token is {token.formatted_token}.\n\n"
                    f"Please remain nearby."
                ),
                None,
                [recipient],
                fail_silently=False
            )
            print(f"Queue Started email sent successfully to {recipient}")
            NotificationLog.objects.create(token=token, notification_type='Queue Started')
        except Exception as e:
            print(f"Exception caught sending Queue Started email to {recipient}:")
            import traceback
            traceback.print_exc()

def send_milestone_notification(current_token_number, doctor_name):
    # Notify all waiting patients of this doctor with an email address
    waiting_tokens = QueueToken.objects.filter(
        status__in=[TokenStatus.WAITING, TokenStatus.NEAR_TURN],
        doctor_name=doctor_name,
        email__isnull=False
    ).exclude(email='')

    print(f"send_milestone_notification called for current token: {current_token_number}, doctor: {doctor_name}, waiting tokens: {[t.formatted_token for t in waiting_tokens]}")
    for token in waiting_tokens:
        log_type = f'Milestone {current_token_number}'
        # Check to prevent duplicate milestone notifications for the same token number
        if not NotificationLog.objects.filter(token=token, notification_type=log_type).exists():
            recipient = token.email
            print(f"Sending Milestone {current_token_number} email to {recipient}")
            try:
                send_mail(
                    f"Queue Milestone: Token {current_token_number} - TMS Portal",
                    (
                        f"Dear {token.full_name},\n\n"
                        f"The queue has reached a milestone. Token {current_token_number} is currently being called.\n"
                        f"Your token is {token.formatted_token}. Please remain nearby."
                    ),
                    None,
                    [recipient],
                    fail_silently=False
                )
                print(f"Milestone {current_token_number} email sent successfully to {recipient}")
                NotificationLog.objects.create(token=token, notification_type=log_type)
            except Exception as e:
                print(f"Exception caught sending Milestone {current_token_number} email to {recipient}:")
                import traceback
                traceback.print_exc()

def send_near_turn_notification(token):
    recipient = token.email
    print(f"send_near_turn_notification called for token: {token.formatted_token}, email: {recipient}")
    if recipient:
        print(f"Sending Near Turn email to {recipient}")
        try:
            send_mail(
                "Your Turn is Approaching - TMS Portal",
                (
                    f"Dear {token.full_name},\n\n"
                    f"Your turn is approaching. Please be ready."
                ),
                None,
                [recipient],
                fail_silently=False
            )
            print(f"Near Turn email sent successfully to {recipient}")
            NotificationLog.objects.create(token=token, notification_type='Near Turn')
        except Exception as e:
            print(f"Exception caught sending Near Turn email to {recipient}:")
            import traceback
            traceback.print_exc()

def send_countdown_notification(token, remaining_count):
    recipient = token.email
    print(f"send_countdown_notification called for token: {token.formatted_token}, remaining: {remaining_count}, email: {recipient}")
    if recipient:
        log_type = f'Countdown {remaining_count}'
        print(f"Sending Countdown {remaining_count} email to {recipient}")
        try:
            send_mail(
                f"Final Countdown: {remaining_count} Left - TMS Portal",
                (
                    f"Dear {token.full_name},\n\n"
                    f"Exactly {remaining_count} patient(s) remain before your turn.\n"
                    f"Please prepare for your consultation."
                ),
                None,
                [recipient],
                fail_silently=False
            )
            print(f"Countdown {remaining_count} email sent successfully to {recipient}")
            NotificationLog.objects.create(token=token, notification_type=log_type)
        except Exception as e:
            print(f"Exception caught sending Countdown {remaining_count} email to {recipient}:")
            import traceback
            traceback.print_exc()

def send_final_call_notification(token):
    recipient = token.email
    print(f"send_final_call_notification called for token: {token.formatted_token}, email: {recipient}")
    if recipient:
        print(f"Sending Final Call email to {recipient}")
        try:
            send_mail(
                "Final Call - TMS Portal",
                (
                    f"Dear {token.full_name},\n\n"
                    f"Please proceed to the consultation area."
                ),
                None,
                [recipient],
                fail_silently=False
            )
            print(f"Final Call email sent successfully to {recipient}")
            NotificationLog.objects.create(token=token, notification_type='Final Call')
        except Exception as e:
            print(f"Exception caught sending Final Call email to {recipient}:")
            import traceback
            traceback.print_exc()
