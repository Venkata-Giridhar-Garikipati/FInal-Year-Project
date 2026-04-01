from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from student_portal.models import CustomUser, Application
from .models import Internship, LearnClass


def mentor_login(request):
    if request.user.is_authenticated and request.user.role == 'mentor':
        return redirect('mentor_dashboard')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user and user.role == 'mentor':
            login(request, user)
            return redirect('mentor_dashboard')
        messages.error(request, 'Invalid credentials or not a mentor account.')
    return render(request, 'mentor_portal/login.html')


def mentor_logout(request):
    logout(request)
    return redirect('mentor_login')


@login_required(login_url='/mentor/login/')
def mentor_dashboard(request):
    if request.user.role != 'mentor':
        return redirect('mentor_login')
    total_internships = Internship.objects.filter(mentor=request.user).count()
    total_classes = LearnClass.objects.filter(mentor=request.user).count()
    total_applications = Application.objects.filter(internship__mentor=request.user).count()
    pending_applications = Application.objects.filter(internship__mentor=request.user, status='pending').count()
    approved_applications = Application.objects.filter(internship__mentor=request.user, status='approved').count()
    rejected_applications = Application.objects.filter(internship__mentor=request.user, status='rejected').count()
    recent_applications = Application.objects.filter(
        internship__mentor=request.user
    ).select_related('student', 'internship').order_by('-applied_at')[:5]
    context = {
        'total_internships': total_internships,
        'total_classes': total_classes,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'recent_applications': recent_applications,
    }
    return render(request, 'mentor_portal/dashboard.html', context)


@login_required(login_url='/mentor/login/')
def create_internship(request):
    if request.user.role != 'mentor':
        return redirect('mentor_login')
    if request.method == 'POST':
        data = request.POST
        required_fields = ['title', 'company_name', 'sector', 'description', 'location',
                           'mode', 'duration', 'stipend_amount', 'openings',
                           'skills_required', 'qualification_required', 'age_min', 'age_max']
        errors = []
        for field in required_fields:
            if not data.get(field, '').strip():
                errors.append(field)
        if errors:
            messages.error(request, f'Please fill all required fields: {", ".join(errors)}')
            return render(request, 'mentor_portal/create_internship.html', {'post': data})

        try:
            internship = Internship.objects.create(
                mentor=request.user,
                title=data.get('title').strip(),
                company_name=data.get('company_name').strip(),
                sector=data.get('sector'),
                description=data.get('description').strip(),
                responsibilities=data.get('responsibilities', '').strip(),
                location=data.get('location').strip(),
                mode=data.get('mode'),
                duration=data.get('duration'),
                stipend_amount=int(data.get('stipend_amount', 5000)),
                openings=int(data.get('openings', 1)),
                last_date_to_apply=data.get('last_date_to_apply') or None,
                skills_required=data.get('skills_required').strip(),
                qualification_required=data.get('qualification_required'),
                eligibility=data.get('eligibility', '').strip(),
                age_min=int(data.get('age_min', 18)),
                age_max=int(data.get('age_max', 25)),
                perks=data.get('perks', '').strip(),
                learning_outcomes=data.get('learning_outcomes', '').strip(),
                contact_email=data.get('contact_email', '').strip(),
                contact_phone=data.get('contact_phone', '').strip(),
            )
            messages.success(request, f'Internship "{internship.title}" created successfully.')
            return redirect('view_applications')
        except Exception as e:
            messages.error(request, f'Error creating internship: {str(e)}')

    return render(request, 'mentor_portal/create_internship.html', {'post': {}})


@login_required(login_url='/mentor/login/')
def view_applications(request):
    if request.user.role != 'mentor':
        return redirect('mentor_login')
    internships = Internship.objects.filter(
        mentor=request.user
    ).prefetch_related('applications__student').order_by('-created_at')
    return render(request, 'mentor_portal/applications.html', {'internships': internships})


@login_required(login_url='/mentor/login/')
def update_application(request, pk):
    if request.user.role != 'mentor':
        return redirect('mentor_login')
    application = get_object_or_404(Application, pk=pk, internship__mentor=request.user)
    if request.method == 'POST':
        status = request.POST.get('status', '').strip()
        feedback = request.POST.get('feedback', '').strip()
        status_message = request.POST.get('status_message', '').strip()

        if status not in ('approved', 'rejected', 'pending'):
            messages.error(request, 'Invalid status selected.')
            return render(request, 'mentor_portal/update_application.html', {'application': application})

        if status in ('approved', 'rejected') and not status_message:
            messages.error(request, f'Please provide a reason/message for {status} status.')
            return render(request, 'mentor_portal/update_application.html', {'application': application})

        application.status = status
        application.status_message = status_message
        if feedback:
            application.mentor_feedback = feedback
        application.save()
        messages.success(request, f'Application {status.upper()} successfully.')
        return redirect('view_applications')

    return render(request, 'mentor_portal/update_application.html', {'application': application})


@login_required(login_url='/mentor/login/')
def create_class(request):
    if request.user.role != 'mentor':
        return redirect('mentor_login')
    if request.method == 'POST':
        data = request.POST
        required_fields = ['title', 'category', 'level', 'description', 'format',
                           'duration_hours', 'total_sessions', 'language']
        errors = []
        for field in required_fields:
            if not data.get(field, '').strip():
                errors.append(field)
        if errors:
            messages.error(request, f'Please fill all required fields: {", ".join(errors)}')
            return render(request, 'mentor_portal/create_class.html', {'post': data})

        try:
            cls = LearnClass.objects.create(
                mentor=request.user,
                title=data.get('title').strip(),
                category=data.get('category'),
                level=data.get('level'),
                description=data.get('description').strip(),
                what_you_will_learn=data.get('what_you_will_learn', '').strip(),
                format=data.get('format'),
                duration_hours=float(data.get('duration_hours', 1.0)),
                total_sessions=int(data.get('total_sessions', 1)),
                schedule=data.get('schedule', '').strip(),
                language=data.get('language', 'English').strip(),
                prerequisites=data.get('prerequisites', '').strip(),
                target_audience=data.get('target_audience', '').strip(),
                max_students=int(data.get('max_students', 50)),
                resources_link=data.get('resources_link', '').strip(),
                join_link=data.get('join_link', '').strip(),
            )
            messages.success(request, f'Class "{cls.title}" created successfully.')
            return redirect('mentor_dashboard')
        except Exception as e:
            messages.error(request, f'Error creating class: {str(e)}')

    return render(request, 'mentor_portal/create_class.html', {'post': {}})


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
import json

from student_portal.models import CustomUser
from student_portal.models import Message


# ─── MENTOR VIEWS ─────────────────────────────────────────────────────────────

@login_required
def mentor_student_list(request):
    """Mentor sees all students with unread message counts."""
    students = CustomUser.objects.filter(role='student', is_active=True)
    student_data = []
    for student in students:
        unread = Message.unread_count(receiver=request.user, sender=student)
        last_msg = Message.objects.filter(
            sender__in=[request.user, student],
            receiver__in=[request.user, student]
        ).order_by('-created_at').first()
        student_data.append({
            'user': student,
            'unread': unread,
            'last_message': last_msg,
        })
    student_data.sort(key=lambda x: (-x['unread'], x['user'].full_name))
    return render(request, 'mentor_portal/mentor_student_list.html', {'students': student_data})


@login_required
def mentor_chat(request, student_id):
    """Mentor chats with a specific student."""
    student = get_object_or_404(CustomUser, id=student_id, role='student')
    Message.mark_as_read(receiver=request.user, sender=student)
    messages = Message.get_conversation(request.user, student)
    return render(request, 'mentor_portal/mentor_chat.html', {
        'other_user': student,
        'messages': messages,
        'current_user': request.user,
    })


# ─── SHARED AJAX ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def send_message(request):
    data = json.loads(request.body)
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Empty message'}, status=400)

    receiver = get_object_or_404(CustomUser, id=receiver_id)
    msg = Message.objects.create(sender=request.user, receiver=receiver, content=content)
    return JsonResponse({
        'id': msg.id,
        'content': msg.content,
        'created_at': msg.created_at.strftime('%I:%M %p'),
        'sender_name': msg.sender.full_name,
    })


@login_required
def poll_messages(request, other_user_id):
    """Long-poll: return new messages after a given message ID."""
    after_id = int(request.GET.get('after', 0))
    other_user = get_object_or_404(CustomUser, id=other_user_id)
    Message.mark_as_read(receiver=request.user, sender=other_user)
    messages = Message.get_conversation(request.user, other_user).filter(id__gt=after_id)
    data = [{
        'id': m.id,
        'content': m.content,
        'is_mine': m.sender == request.user,
        'sender_name': m.sender.full_name,
        'created_at': m.created_at.strftime('%I:%M %p'),
    } for m in messages]
    return JsonResponse({'messages': data})
