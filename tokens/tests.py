from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from tokens.models import QueueToken, UserProfile, TokenStatus, NotificationLog

class QueueStartedNotificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create nurse user
        self.nurse_user = User.objects.create_user(
            username='nurse@example.com',
            email='nurse@example.com',
            password='password123'
        )
        UserProfile.objects.create(
            user=self.nurse_user,
            role='nurse'
        )
        
        # Log in the nurse
        self.client.login(username='nurse@example.com', password='password123')
        
        # Setup tokens for Doctor A (Helen Vance)
        self.hel1 = QueueToken.objects.create(
            token_number=1,
            full_name='Helen Patient 1',
            email='helen_p1@example.com',
            mobile_number='1234567890',
            department='General Medicine',
            doctor_name='Dr. Helen Vance',
            status='WAITING'
        )
        self.hel2 = QueueToken.objects.create(
            token_number=2,
            full_name='Helen Patient 2',
            email='helen_p2@example.com',
            mobile_number='1234567890',
            department='General Medicine',
            doctor_name='Dr. Helen Vance',
            status='WAITING'
        )
        self.hel3 = QueueToken.objects.create(
            token_number=3,
            full_name='Helen Patient 3',
            email='helen_p3@example.com',
            mobile_number='1234567890',
            department='General Medicine',
            doctor_name='Dr. Helen Vance',
            status='WAITING'
        )

        # Setup tokens for Doctor B (Sarah Patel)
        self.sar1 = QueueToken.objects.create(
            token_number=1,
            full_name='Sarah Patient 1',
            email='sarah_p1@example.com',
            mobile_number='0987654321',
            department='Cardiology',
            doctor_name='Dr. Sarah Patel',
            status='WAITING'
        )
        self.sar2 = QueueToken.objects.create(
            token_number=2,
            full_name='Sarah Patient 2',
            email='sarah_p2@example.com',
            mobile_number='0987654321',
            department='Cardiology',
            doctor_name='Dr. Sarah Patel',
            status='WAITING'
        )

    def test_calling_token_1_triggers_queue_started_once(self):
        """
        Calling Token 1 for Dr. Helen Vance should trigger Queue Started
        emails to all waiting patients of Dr. Helen Vance.
        """
        mail.outbox = []
        
        # Call Helen Patient 1 (Token 1)
        response = self.client.post(reverse('call_patient', args=[self.hel1.id]))
        self.assertEqual(response.status_code, 302) # Redirect to nurse_dashboard
        
        # Refresh tokens from DB
        self.hel1.refresh_from_db()
        self.assertEqual(self.hel1.status, 'CALLED')
        
        # Verify emails:
        emails_sent = mail.outbox
        
        # We expect:
        # - 1 Final Call for Helen Patient 1
        # - 2 Queue Started for Helen Patient 2 and 3
        # - 1 Countdown 1 for Helen Patient 2
        # - 1 Countdown 2 for Helen Patient 3
        # (Total 5 emails)
        self.assertEqual(len(emails_sent), 5)
        
        # Check that Queue Started was sent to helen_p2 and helen_p3
        queue_started_recipients = [m.to[0] for m in emails_sent if "Queue Started" in m.subject]
        self.assertEqual(len(queue_started_recipients), 2)
        self.assertIn('helen_p2@example.com', queue_started_recipients)
        self.assertIn('helen_p3@example.com', queue_started_recipients)
        
        # Check NotificationLog records
        self.assertTrue(NotificationLog.objects.filter(token=self.hel2, notification_type='Queue Started').exists())
        self.assertTrue(NotificationLog.objects.filter(token=self.hel3, notification_type='Queue Started').exists())

    def test_calling_token_1_again_does_not_trigger_queue_started_again(self):
        """
        Re-calling Token 1 for Dr. Helen Vance should not trigger Queue Started again.
        """
        # Call Helen Patient 1 first time
        self.client.post(reverse('call_patient', args=[self.hel1.id]))
        
        # Clear outbox
        mail.outbox = []
        
        # Call Helen Patient 1 second time
        response = self.client.post(reverse('call_patient', args=[self.hel1.id]))
        self.assertEqual(response.status_code, 302)
        
        # Verify no Queue Started email is in outbox, only Final Call might be re-sent
        emails_sent = mail.outbox
        queue_started_emails = [m for m in emails_sent if "Queue Started" in m.subject]
        self.assertEqual(len(queue_started_emails), 0)

    def test_calling_token_2_directly_does_not_trigger_queue_started(self):
        """
        Calling Token 2 of Dr. Helen Vance (even as the first call) should not trigger Queue Started.
        """
        mail.outbox = []
        
        # Call Helen Patient 2 (Token 2) first
        response = self.client.post(reverse('call_patient', args=[self.hel2.id]))
        self.assertEqual(response.status_code, 302)
        
        # Verify emails: only Final Call for hel2 and countdown for hel3, no Queue Started
        emails_sent = mail.outbox
        queue_started_emails = [m for m in emails_sent if "Queue Started" in m.subject]
        self.assertEqual(len(queue_started_emails), 0)

    def test_doctor_queue_isolation(self):
        """
        Triggering Queue Started for Dr. Helen Vance should not trigger it for Dr. Sarah Patel.
        """
        mail.outbox = []
        
        # Call Helen Patient 1 (Token 1)
        self.client.post(reverse('call_patient', args=[self.hel1.id]))
        
        # Emails in outbox should not contain any for Sarah's patients
        emails_sent = mail.outbox
        recipients = [m.to[0] for m in emails_sent]
        self.assertNotIn('sarah_p1@example.com', recipients)
        self.assertNotIn('sarah_p2@example.com', recipients)
        
        # Now call Sarah Patient 1 (Token 1)
        mail.outbox = []
        self.client.post(reverse('call_patient', args=[self.sar1.id]))
        
        # Sarah Patient 2 should get Queue Started email (since she is waiting for Dr. Sarah Patel)
        emails_sent = mail.outbox
        queue_started_recipients = [m.to[0] for m in emails_sent if "Queue Started" in m.subject]
        self.assertEqual(len(queue_started_recipients), 1)
        self.assertIn('sarah_p2@example.com', queue_started_recipients)
        self.assertNotIn('helen_p2@example.com', queue_started_recipients)

class DoctorSelectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create nurse user
        self.nurse_user = User.objects.create_user(
            username='nurse@example.com',
            email='nurse@example.com',
            password='password123'
        )
        UserProfile.objects.create(
            user=self.nurse_user,
            role='nurse'
        )
        self.client.login(username='nurse@example.com', password='password123')
        
        # Create doctor users
        self.doc_helen_user = User.objects.create_user(
            username='helen@example.com',
            email='helen@example.com',
            password='password123',
            first_name='Dr. Helen Vance'
        )
        self.doc_helen_profile = UserProfile.objects.create(
            user=self.doc_helen_user,
            role='doctor',
            department='General Medicine'
        )
        
        self.doc_sarah_user = User.objects.create_user(
            username='sarah@example.com',
            email='sarah@example.com',
            password='password123',
            first_name='Dr. Sarah Patel'
        )
        self.doc_sarah_profile = UserProfile.objects.create(
            user=self.doc_sarah_user,
            role='doctor',
            department='Cardiology'
        )

    def test_valid_doctor_and_department_registration(self):
        """
        Registering a patient with a doctor assigned to the selected department should succeed.
        """
        response = self.client.post(reverse('nurse_dashboard'), {
            'full_name': 'John Doe',
            'mobile_number': '1112223333',
            'email': 'john@example.com',
            'department': 'General Medicine',
            'doctor_name': 'Dr. Helen Vance'
        })
        self.assertEqual(response.status_code, 302) # Redirects to dashboard on success
        
        # Verify token created in DB
        self.assertTrue(QueueToken.objects.filter(
            full_name='John Doe',
            doctor_name='Dr. Helen Vance',
            department='General Medicine'
        ).exists())

    def test_invalid_doctor_and_department_registration_rejected(self):
        """
        Registering a patient with a doctor who does not belong to the selected department should fail.
        """
        response = self.client.post(reverse('nurse_dashboard'), {
            'full_name': 'John Doe',
            'mobile_number': '1112223333',
            'email': 'john@example.com',
            'department': 'Cardiology',
            'doctor_name': 'Dr. Helen Vance' # Helen is General Medicine, not Cardiology!
        })
        self.assertEqual(response.status_code, 200) # Re-renders dashboard with error
        self.assertContains(response, 'The selected doctor does not belong to the selected department.')
        
        # Verify no token created in DB
        self.assertFalse(QueueToken.objects.filter(
            full_name='John Doe',
            doctor_name='Dr. Helen Vance',
            department='Cardiology'
        ).exists())
