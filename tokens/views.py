from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Max
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Patient, Token, UserProfile
from .services import (
    send_queue_started_notification,
    send_milestone_notification,
    send_near_turn_notification,
    send_countdown_notification,
    send_final_call_notification
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
        
        # Always create a new Patient record on form submission
        patient = Patient.objects.create(full_name=full_name, mobile_number=mobile_number, email=email)
            
        # Determine sequential token number starting at 1 for the selected doctor
        max_num = Token.objects.filter(doctor_name=doctor_name).aggregate(Max('token_number'))['token_number__max']
        next_token_number = (max_num or 0) + 1
        
        # Enqueue new token
        Token.objects.create(
            token_number=next_token_number,
            patient=patient,
            department=department,
            doctor_name=doctor_name,
            status='WAITING'
        )
        return redirect('nurse_dashboard')

    # GET request
    tokens = Token.objects.all().order_by('id')
    
    # Calculate statistics
    waiting_count = Token.objects.filter(status__in=['WAITING', 'NEAR_TURN']).count()
    called_count = Token.objects.filter(status='CALLED').count()
    completed_count = Token.objects.filter(status='COMPLETED').count()
    total_count = tokens.count()
    
    # Now serving token details
    now_serving = Token.objects.filter(status='CALLED').order_by('-called_at').first()

    context = {
        'tokens': tokens,
        'waiting_count': waiting_count,
        'called_count': called_count,
        'completed_count': completed_count,
        'total_count': total_count,
        'now_serving': now_serving,
    }
    return render(request, 'nurse_dashboard.html', context)

from django.shortcuts import get_object_or_404
from django.utils import timezone

@login_required(login_url='login')
def call_patient(request, token_id):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'nurse')):
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        # Retrieve the token first to get doctor details
        token = get_object_or_404(Token, id=token_id)
        doctor_name = token.doctor_name

        # Check if this will be the first token called for this doctor (no previously called or completed tokens exist for this doctor)
        already_called_count = Token.objects.filter(
            status__in=['CALLED', 'COMPLETED'],
            doctor_name=doctor_name
        ).exclude(id=token_id).count()
        is_first_call = (already_called_count == 0)
        
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
        waiting_tokens = Token.objects.filter(
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
            
            # Trigger Near Turn at exactly 5 separation
            if diff == 5:
                if not NotificationLog.objects.filter(token=wt, notification_type='Near Turn').exists():
                    print("NEAR TURN notification triggered")
                    send_near_turn_notification(wt)
            
            # Trigger Countdown at exactly 3, 2, or 1 separation
            elif diff in [1, 2, 3]:
                log_type = f'Countdown {diff}'
                if not NotificationLog.objects.filter(token=wt, notification_type=log_type).exists():
                    print(f"COUNTDOWN {diff} notification triggered")
                    send_countdown_notification(wt, diff)
        
    return redirect('nurse_dashboard')

@login_required(login_url='login')
def doctor_dashboard(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'doctor')):
        return redirect_dashboard_by_role(request.user)
        
    # Filter tokens belonging to the logged-in doctor
    doctor_name_query = request.user.first_name or request.user.username
    cleaned_name = doctor_name_query.replace("Dr. ", "").replace("Dr ", "").strip()
    
    from django.db.models import Q
    tokens = Token.objects.filter(
        Q(doctor_name__icontains=cleaned_name) |
        Q(doctor_name__icontains=doctor_name_query)
    ).order_by('token_number')
    
    # Calculate statistics using only this doctor's tokens
    waiting_count = tokens.filter(status__in=['WAITING', 'NEAR_TURN']).count()
    completed_count = tokens.filter(status='COMPLETED').count()
    skipped_count = tokens.filter(status='SKIPPED').count()
    total_count = tokens.count()
    
    # Calculate average wait time (in minutes) for completed cases
    completed_tokens = tokens.filter(status='COMPLETED', completed_at__isnull=False)
    completed_list = list(completed_tokens)
    if completed_list:
        total_wait = sum((t.completed_at - t.created_at).total_seconds() for t in completed_list)
        avg_wait_mins = int(total_wait / (60 * len(completed_list)))
    else:
        avg_wait_mins = 0
 
    # Live active session token for this doctor
    current_token = tokens.filter(status='CALLED').order_by('-called_at').first()
    
    # Next token for this doctor
    next_token = tokens.filter(status='WAITING').order_by('token_number').first()
    
    context = {
        'tokens': tokens,
        'waiting_count': waiting_count,
        'completed_count': completed_count,
        'skipped_count': skipped_count,
        'total_count': total_count,
        'avg_wait_mins': avg_wait_mins,
        'current_token': current_token,
        'next_token': next_token,
    }
    return render(request, 'doctor_dashboard.html', context)


@login_required(login_url='login')
def complete_trip(request, token_id):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'nurse')):
        return redirect_dashboard_by_role(request.user)
        
    if request.method == 'POST':
        token = get_object_or_404(Token, id=token_id)
        token.status = 'COMPLETED'
        token.completed_at = timezone.now()
        token.save()
        
    return redirect('nurse_dashboard')
