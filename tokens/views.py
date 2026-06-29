from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Max
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import QueueToken, UserProfile
from .services import (
    send_queue_started_notification,
    send_milestone_notification,
    send_near_turn_notification,
    send_final_call_notification,
    send_registration_notification
)

def redirect_dashboard_by_role(user):
    if user.is_superuser:
        return redirect('/admin/')
    try:
        profile = user.profile
        if profile.role == 'doctor':
            return redirect('doctor_dashboard')
        elif profile.role == 'nurse':
            return redirect('nurse_dashboard')
    except UserProfile.DoesNotExist:
        if user.is_staff:
            return redirect('/admin/')
    return redirect('login')

def register_user(request):
    if request.user.is_authenticated:
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        department = request.POST.get('department')
        license_number = request.POST.get('license')
        
        if not role or role not in ['doctor', 'nurse']:
            return render(request, 'register.html', {'error': 'Invalid role selected.'})
            
        if User.objects.filter(username=email).exists():
            return render(request, 'register.html', {'error': 'A user with this email already exists.'})
            
        try:
            # Create user using email as the username
            user = User.objects.create_user(username=email, email=email, password=password)
            user.first_name = full_name
            user.save()
            
            UserProfile.objects.create(
                user=user,
                role=role,
                department=department,
                license_number=license_number
            )
            
            # Automatically log the user in after registration
            login(request, user)
            return redirect_dashboard_by_role(user)
        except Exception as e:
            return render(request, 'register.html', {'error': f'Registration failed: {str(e)}'})
            
    return render(request, 'register.html')

def login_user(request):
    if request.user.is_authenticated:
        return redirect_dashboard_by_role(request.user)

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect_dashboard_by_role(user)
        else:
            return render(request, 'login.html', {'error': 'Invalid email or password.'})
            
    return render(request, 'login.html')

def landing_page(request):
    if request.user.is_authenticated:
        return redirect_dashboard_by_role(request.user)
    return render(request, 'landing.html')

def logout_user(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def nurse_dashboard(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'nurse')):
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        mobile_number = request.POST.get('mobile_number')
        email = request.POST.get('email') or None
        department = request.POST.get('department')
        doctor_name = request.POST.get('doctor_name')

        # Validate that the selected doctor belongs to the selected department
        from django.db.models import Q
        # Define department normalization mapping to support different DB values
        dept_normalization = {
            'General Medicine': ['General Medicine', 'general'],
            'Cardiology': ['Cardiology', 'cardiology'],
            'Neurology': ['Neurology', 'neurology'],
            'Pediatrics': ['Pediatrics', 'pediatrics'],
            'Orthopedics': ['Orthopedics', 'orthopedics'],
            'Dermatology': ['Dermatology', 'dermatology'],
            'Emergency': ['Emergency', 'emergency'],
            'Surgery': ['Surgery', 'surgery'],
        }
        allowed_depts = dept_normalization.get(department, [department])

        doctor_profile = UserProfile.objects.filter(
            role='doctor',
            department__in=allowed_depts
        ).filter(
            Q(user__first_name=doctor_name) | Q(user__username=doctor_name)
        ).first()

        if not doctor_profile:
            tokens = QueueToken.objects.all().order_by('id')
            doctors = UserProfile.objects.filter(role='doctor').select_related('user')
            waiting_count = QueueToken.objects.filter(status__in=['WAITING', 'NEAR_TURN']).count()
            called_count = QueueToken.objects.filter(status='CALLED').count()
            total_count = tokens.count()
            now_serving = QueueToken.objects.filter(status='CALLED').order_by('-called_at').first()
            context = {
                'tokens': tokens,
                'waiting_count': waiting_count,
                'called_count': called_count,
                'total_count': total_count,
                'now_serving': now_serving,
                'doctors': doctors,
                'error': 'The selected doctor does not belong to the selected department.'
            }
            return render(request, 'nurse_dashboard.html', context)

        from .models import CompletedAppointment
        today = timezone.localdate()
        total_tokens_today = QueueToken.objects.filter(created_at__date=today).count()
        total_tokens_today += CompletedAppointment.objects.filter(date=today).count()

        if total_tokens_today >= 1000:
            tokens = QueueToken.objects.all().order_by('id')
            doctors = UserProfile.objects.filter(role='doctor').select_related('user')
            waiting_count = QueueToken.objects.filter(status__in=['WAITING', 'NEAR_TURN']).count()
            called_count = QueueToken.objects.filter(status='CALLED').count()
            total_count = tokens.count()
            now_serving = QueueToken.objects.filter(status='CALLED').order_by('-called_at').first()
            context = {
                'tokens': tokens,
                'waiting_count': waiting_count,
                'called_count': called_count,
                'total_count': total_count,
                'now_serving': now_serving,
                'doctors': doctors,
                'error': 'Daily appointment limit of 1000 reached.'
            }
            return render(request, 'nurse_dashboard.html', context)

        # Determine sequential token number — resets daily per doctor
        today = timezone.localdate()
        max_num = QueueToken.objects.filter(
            doctor_name=doctor_name,
            created_at__date=today
        ).aggregate(Max('token_number'))['token_number__max']
        next_token_number = (max_num or 0) + 1

        # Create a single unified QueueToken record
        token = QueueToken.objects.create(
            token_number=next_token_number,
            full_name=full_name,
            mobile_number=mobile_number,
            email=email,
            department=department,
            doctor_name=doctor_name,
            status='WAITING'
        )

        # Send registration confirmation email if patient has an email address
        send_registration_notification(token)

        return redirect('nurse_dashboard')

    # GET request
    tokens = QueueToken.objects.all().order_by('id')
    doctors = UserProfile.objects.filter(role='doctor').select_related('user')

    # Calculate statistics (active queue only — completed records are deleted)
    waiting_count = QueueToken.objects.filter(status__in=['WAITING', 'NEAR_TURN']).count()
    called_count = QueueToken.objects.filter(status='CALLED').count()
    total_count = tokens.count()

    # Now serving token details
    now_serving = QueueToken.objects.filter(status='CALLED').order_by('-called_at').first()

    context = {
        'tokens': tokens,
        'waiting_count': waiting_count,
        'called_count': called_count,
        'total_count': total_count,
        'now_serving': now_serving,
        'doctors': doctors,
    }
    return render(request, 'nurse_dashboard.html', context)


@login_required(login_url='login')
def call_patient(request, token_id):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ('nurse', 'doctor'))):
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        # Retrieve the token first to get doctor details
        token = get_object_or_404(QueueToken, id=token_id)
        doctor_name = token.doctor_name

        # Send Queue Started only once, when Token Number 1 is called for the first time
        is_first_call = (token.token_number == 1 and token.status != 'CALLED')

        # Call the chosen token
        token.status = 'CALLED'
        token.called_at = timezone.now()
        token.save()

        C = token.token_number

        # Trigger Queue Started if this is the first token call for this doctor
        if is_first_call:
            print("QUEUE STARTED notification triggered")
            send_queue_started_notification(doctor_name)

        # Trigger Final Call for the called patient
        print("FINAL CALL notification triggered")
        send_final_call_notification(token)

        # Trigger Milestone if current token is a multiple of 10 for this doctor
        if C % 10 == 0:
            print("MILESTONE notification triggered")
            send_milestone_notification(C, doctor_name)

        # Scan and update remaining waiting tokens for this doctor only
        from .models import NotificationLog
        waiting_tokens = QueueToken.objects.filter(
            status__in=['WAITING', 'NEAR_TURN'],
            doctor_name=doctor_name
        ).order_by('token_number')
        for wt in waiting_tokens:
            diff = wt.token_number - C

            # Map status badge for NEAR_TURN
            if diff <= 5:
                if wt.status == 'WAITING':
                    wt.status = 'NEAR_TURN'
                    wt.save()

            if diff == 5:
                if not NotificationLog.objects.filter(token=wt, notification_type='Near Turn').exists():
                    print("NEAR TURN notification triggered")
                    send_near_turn_notification(wt)

    # Redirect back to the appropriate dashboard based on user role
    if hasattr(request.user, 'profile') and request.user.profile.role == 'doctor':
        return redirect('doctor_dashboard')
    return redirect('nurse_dashboard')

@login_required(login_url='login')
def doctor_dashboard(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'doctor')):
        return redirect_dashboard_by_role(request.user)
        
    # Filter tokens belonging to the logged-in doctor
    doctor_name_query = request.user.first_name or request.user.username
    cleaned_name = doctor_name_query.replace("Dr. ", "").replace("Dr ", "").strip()

    from django.db.models import Q
    tokens = QueueToken.objects.filter(
        Q(doctor_name__icontains=cleaned_name) |
        Q(doctor_name__icontains=doctor_name_query)
    ).order_by('token_number')

    # Statistics — active queue only (no completed records remain in DB)
    waiting_count = tokens.filter(status__in=['WAITING', 'NEAR_TURN']).count()
    skipped_count = tokens.filter(status='SKIPPED').count()
    total_count = tokens.count()

    # Live active session token for this doctor
    current_token = tokens.filter(status='CALLED').order_by('-called_at').first()

    # Next token for this doctor
    next_token = tokens.filter(status__in=['WAITING', 'NEAR_TURN']).order_by('token_number').first()

    context = {
        'tokens': tokens,
        'waiting_count': waiting_count,
        'skipped_count': skipped_count,
        'total_count': total_count,
        'current_token': current_token,
        'next_token': next_token,
    }
    return render(request, 'doctor_dashboard.html', context)


@login_required(login_url='login')
def complete_trip(request, token_id):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'nurse')):
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        token = get_object_or_404(QueueToken, id=token_id)
        from .models import CompletedAppointment
        CompletedAppointment.objects.create(
            token_number=token.formatted_token,
            patient_name=token.full_name,
            doctor_name=token.doctor_name
        )
        token.delete()

    return redirect('nurse_dashboard')


@login_required(login_url='login')
def complete_case_doctor(request, token_id):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'doctor')):
        return redirect_dashboard_by_role(request.user)

    if request.method == 'POST':
        token = get_object_or_404(QueueToken, id=token_id)
        from .models import CompletedAppointment
        CompletedAppointment.objects.create(
            token_number=token.formatted_token,
            patient_name=token.full_name,
            doctor_name=token.doctor_name
        )
        token.delete()

    return redirect('doctor_dashboard')

@login_required(login_url='login')
def clear_queue(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'nurse')):
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        QueueToken.objects.all().delete()
        
    return redirect('nurse_dashboard')
