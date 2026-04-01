from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser


def home(request):
    return render(request, 'student_portal/home.html')


def about(request):
    return render(request, 'student_portal/about.html')


def register(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    tech_stack = [
        "Python",
        "Django",
        "scikit-learn",
        "NLP",
        "TF-IDF",
        "Pandas",
        "Tailwind CSS",
        "SQLite"
    ]

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not full_name or not email or not password:
            messages.error(request, 'All fields are required.')
            return render(request, 'student_portal/register.html', {
                'tech_stack': tech_stack
            })

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'student_portal/register.html', {
                'tech_stack': tech_stack
            })

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'student_portal/register.html', {
                'tech_stack': tech_stack
            })

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'student_portal/register.html', {
                'tech_stack': tech_stack
            })

        CustomUser.objects.create_user(
            email=email,
            full_name=full_name,
            password=password,
            role='student'
        )

        messages.success(request, 'Registration successful! Please login.')
        return redirect('student_login')

    return render(request, 'student_portal/register.html', {
        'tech_stack': tech_stack
    })


import os
import csv
import json
import tempfile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from .models import CustomUser, Feedback, Application, PredictionResult
from mentor_portal.models import Internship, LearnClass


# ─── Auth Views ───────────────────────────────────────────────────────────────

def student_login(request):
    if request.user.is_authenticated and request.user.role == 'student':
        return redirect('student_dashboard')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user and user.role == 'student':
            login(request, user)
            return redirect('student_dashboard')
        messages.error(request, 'Invalid credentials or not a student account.')
    return render(request, 'student_portal/login.html')


def student_register(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        if not full_name or not email or not password:
            messages.error(request, 'All fields are required.')
        elif password != confirm:
            messages.error(request, 'Passwords do not match.')
        elif CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        else:
            CustomUser.objects.create_user(email=email, full_name=full_name,
                                           password=password, role='student')
            messages.success(request, 'Registered successfully. Please login.')
            return redirect('student_login')
    return render(request, 'student_portal/register.html')


def student_logout(request):
    logout(request)
    return redirect('student_login')


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def student_dashboard(request):
    if request.user.role != 'student':
        return redirect('student_login')
    total_internships = Internship.objects.filter(is_active=True).count()
    total_classes = LearnClass.objects.filter(is_active=True).count()
    my_applications = Application.objects.filter(student=request.user)
    total_applied = my_applications.count()
    pending = my_applications.filter(status='pending').count()
    approved = my_applications.filter(status='approved').count()
    rejected = my_applications.filter(status='rejected').count()
    recent_apps = my_applications.select_related('internship').order_by('-applied_at')[:3]
    total_predictions = PredictionResult.objects.filter(student=request.user).count()
    return render(request, 'student_portal/dashboard.html', {
        'total_internships': total_internships,
        'total_classes': total_classes,
        'total_applied': total_applied,
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'recent_apps': recent_apps,
        'total_predictions': total_predictions,
    })


# ─── Profile ──────────────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def my_profile(request):
    if request.user.role != 'student':
        return redirect('student_login')
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        if full_name:
            request.user.full_name = full_name
            request.user.save()
            messages.success(request, 'Profile updated.')
            return redirect('my_profile')
    return render(request, 'student_portal/profile.html')


# ─── Feedback ─────────────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def submit_feedback(request):
    if request.user.role != 'student':
        return redirect('student_login')
    if request.method == 'POST':
        msg = request.POST.get('message', '').strip()
        if msg:
            Feedback.objects.create(student=request.user, message=msg)
            messages.success(request, 'Feedback submitted.')
            return redirect('submit_feedback')
        messages.error(request, 'Feedback cannot be empty.')
    return render(request, 'student_portal/feedback.html')


# ─── Internships ──────────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def view_internships(request):
    if request.user.role != 'student':
        return redirect('student_login')
    internships = Internship.objects.filter(is_active=True).order_by('-created_at')
    applied_ids = list(Application.objects.filter(
        student=request.user).values_list('internship_id', flat=True))
    return render(request, 'student_portal/internships.html', {
        'internships': internships,
        'applied_ids': applied_ids,
        'total_internships': internships.count(),
        'total_applied': len(applied_ids),
    })


@login_required(login_url='/student/login/')
def apply_internship(request, pk):
    if request.user.role != 'student':
        return redirect('student_login')
    internship = get_object_or_404(Internship, pk=pk, is_active=True)
    if Application.objects.filter(student=request.user, internship=internship).exists():
        messages.warning(request, 'You have already applied to this internship.')
    else:
        Application.objects.create(student=request.user, internship=internship)
        messages.success(request, f'Application submitted for "{internship.title}".')
    # If came from prediction page, redirect back
    next_url = request.GET.get('next', 'view_internships')
    if next_url == 'prediction':
        return redirect('my_predictions')
    return redirect('view_internships')


@login_required(login_url='/student/login/')
def application_status(request):
    if request.user.role != 'student':
        return redirect('student_login')
    apps = Application.objects.filter(
        student=request.user
    ).select_related('internship', 'internship__mentor').order_by('-applied_at')
    return render(request, 'student_portal/application_status.html', {
        'apps': apps,
        'total': apps.count(),
        'pending': apps.filter(status='pending').count(),
        'approved': apps.filter(status='approved').count(),
        'rejected': apps.filter(status='rejected').count(),
    })


# ─── Learn Classes ────────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def learn_classes(request):
    if request.user.role != 'student':
        return redirect('student_login')
    classes = LearnClass.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'student_portal/learn_classes.html', {
        'classes': classes,
        'total_classes': classes.count(),
    })


# ─── Prediction ───────────────────────────────────────────────────────────────
# ─── Prediction ───────────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def prediction(request):
    if request.user.role != 'student':
        return redirect('student_login')

    from . import prediction_engine as pe

    ml_available = pe.models_available()
    result       = None
    error        = None

    if request.method == 'POST':
        resume_file = request.FILES.get('resume_pdf')

        if not resume_file:
            messages.error(request, 'Please upload a PDF resume.')
        elif not resume_file.name.lower().endswith('.pdf'):
            messages.error(request, 'Only PDF files are accepted.')
        elif resume_file.size > 5 * 1024 * 1024:
            messages.error(request, 'File size must be under 5 MB.')
        else:
            import tempfile
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    for chunk in resume_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                # ── Run full prediction (mirrors notebook exactly) ────────────
                pred = pe.run_prediction(tmp_path)
                pred['resume_filename'] = resume_file.name

                # ── Match live mentor internships ─────────────────────────────
                matched = pe.match_mentor_internships(
                    pred['predicted_category'],
                    pred['clean_preview']
                )
                pred['matched_internships'] = matched

                # ── Applied internship IDs (for Apply/Applied buttons) ────────
                pred['applied_ids'] = list(
                    Application.objects.filter(student=request.user)
                    .values_list('internship_id', flat=True)
                )

                # ── Save to DB ────────────────────────────────────────────────
                saved = PredictionResult.objects.create(
                    student=request.user,
                    resume_filename=resume_file.name,
                    predicted_category=pred['predicted_category'],
                    confidence_score=pred.get('confidence_score'),
                    top_categories=pred.get('top3_categories', []),
                    top_jobs=pred.get('top5_jobs', []),
                    matched_internships=matched,
                    words_extracted=pred.get('words_raw', 0),
                    raw_text_preview=pred.get('clean_preview', ''),
                )
                pred['prediction_id'] = saved.id
                result = pred

            except Exception as e:
                error = str(e)
                messages.error(request, f'Prediction failed: {e}')
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    return render(request, 'student_portal/prediction.html', {
        'ml_available': ml_available,
        'result':       result,
        'error':        error,
    })

# ─── My Predictions History ───────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def my_predictions(request):
    if request.user.role != 'student':
        return redirect('student_login')
    predictions = PredictionResult.objects.filter(student=request.user).order_by('-created_at')
    applied_ids = list(Application.objects.filter(
        student=request.user).values_list('internship_id', flat=True))
    return render(request, 'student_portal/my_predictions.html', {
        'predictions': predictions,
        'total_predictions': predictions.count(),
        'applied_ids': applied_ids,
    })


# ─── Prediction Detail ────────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def prediction_detail(request, pk):
    if request.user.role != 'student':
        return redirect('student_login')
    pred = get_object_or_404(PredictionResult, pk=pk, student=request.user)
    applied_ids = list(Application.objects.filter(
        student=request.user).values_list('internship_id', flat=True))
    return render(request, 'student_portal/prediction_detail.html', {
        'pred': pred,
        'applied_ids': applied_ids,
    })


# ─── Download Prediction ──────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def download_prediction(request, pk):
    if request.user.role != 'student':
        return redirect('student_login')
    pred = get_object_or_404(PredictionResult, pk=pk, student=request.user)
    fmt = request.GET.get('format', 'csv')

    if fmt == 'json':
        data = {
            'student': request.user.full_name,
            'email': request.user.email,
            'resume_filename': pred.resume_filename,
            'prediction_date': pred.created_at.strftime('%Y-%m-%d %H:%M'),
            'predicted_category': pred.predicted_category,
            'confidence_score': pred.confidence_score,
            'top_categories': pred.top_categories,
            'top_jobs': pred.top_jobs,
            'matched_internships': pred.matched_internships,
        }
        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="prediction_{pk}.json"'
        return response

    # Default: CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="prediction_{pk}.csv"'
    writer = csv.writer(response)

    writer.writerow(['PM Internship Scheme — Resume Prediction Report'])
    writer.writerow([])
    writer.writerow(['Student Name', request.user.full_name])
    writer.writerow(['Email', request.user.email])
    writer.writerow(['Resume File', pred.resume_filename])
    writer.writerow(['Prediction Date', pred.created_at.strftime('%d %B %Y, %H:%M')])
    writer.writerow([])

    writer.writerow(['PREDICTED CATEGORY', pred.predicted_category])
    if pred.confidence_score:
        writer.writerow(['CONFIDENCE SCORE', f'{pred.confidence_score:.1f}%'])
    writer.writerow([])

    if pred.top_categories:
        writer.writerow(['TOP CATEGORY PREDICTIONS'])
        writer.writerow(['Rank', 'Category', 'Score (%)'])
        for i, cat in enumerate(pred.top_categories, 1):
            writer.writerow([i, cat.get('category', ''), cat.get('score', '')])
        writer.writerow([])

    if pred.top_jobs:
        writer.writerow(['TOP MATCHING JOBS FROM DATASET'])
        writer.writerow(['Rank', 'Job Title', 'Category', 'Location', 'Similarity Score'])
        for job in pred.top_jobs:
            writer.writerow([
                job.get('rank', ''),
                job.get('job_title', ''),
                job.get('category', ''),
                job.get('location', ''),
                job.get('similarity_score', ''),
            ])
        writer.writerow([])

    if pred.matched_internships:
        writer.writerow(['MATCHING MENTOR INTERNSHIPS'])
        writer.writerow(['Rank', 'Title', 'Company', 'Sector', 'Location',
                         'Stipend', 'Duration', 'Match Score', 'Mentor'])
        for i, intern in enumerate(pred.matched_internships, 1):
            writer.writerow([
                i,
                intern.get('title', ''),
                intern.get('company_name', ''),
                intern.get('sector', ''),
                intern.get('location', ''),
                f"Rs.{intern.get('stipend_amount', '')}",
                intern.get('duration', ''),
                f"{intern.get('match_score', '')}%",
                intern.get('mentor_name', ''),
            ])

    return response


# ─── Apply from Prediction ────────────────────────────────────────────────────

@login_required(login_url='/student/login/')
def apply_from_prediction(request, internship_pk, prediction_pk):
    if request.user.role != 'student':
        return redirect('student_login')
    internship = get_object_or_404(Internship, pk=internship_pk, is_active=True)
    if Application.objects.filter(student=request.user, internship=internship).exists():
        messages.warning(request, 'You have already applied to this internship.')
    else:
        Application.objects.create(student=request.user, internship=internship)
        messages.success(request, f'Applied to "{internship.title}" at {internship.company_name}!')
    return redirect('prediction_detail', pk=prediction_pk)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
import json

from student_portal.models import CustomUser
from .models import Message


# ─── STUDENT VIEWS ────────────────────────────────────────────────────────────

@login_required
def student_mentor_list(request):
    """Student sees all mentors with unread message counts."""
    mentors = CustomUser.objects.filter(role='mentor', is_active=True)
    mentor_data = []
    for mentor in mentors:
        unread = Message.unread_count(receiver=request.user, sender=mentor)
        last_msg = Message.objects.filter(
            sender__in=[request.user, mentor],
            receiver__in=[request.user, mentor]
        ).order_by('-created_at').first()
        mentor_data.append({
            'user': mentor,
            'unread': unread,
            'last_message': last_msg,
        })
    # Sort: mentors with unread messages first
    mentor_data.sort(key=lambda x: (-x['unread'], x['user'].full_name))
    return render(request, 'student_portal/student_mentor_list.html', {'mentors': mentor_data})


@login_required
def student_chat(request, mentor_id):
    """Student chats with a specific mentor."""
    mentor = get_object_or_404(CustomUser, id=mentor_id, role='mentor')
    Message.mark_as_read(receiver=request.user, sender=mentor)
    messages = Message.get_conversation(request.user, mentor)
    return render(request, 'student_portal/student_chat.html', {
        'other_user': mentor,
        'messages': messages,
        'current_user': request.user,
    })


import json
import requests
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.conf import settings

from .models import ChatSession, ChatMessage


# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are InternBot, a smart and friendly AI career assistant built exclusively for students on the InternConnect platform.

Your expertise covers:
1. **Career Guidance** — Resume writing, career path advice, interview preparation, skill development, choosing between job offers, career switching tips.
2. **Internship Help** — How to find internships, what to expect, how to perform well, remote vs on-site, stipend negotiation, internship-to-PPO conversion.
3. **Application Support** — How to write cover letters, SOPs, fill applications, what mentors look for, how to stand out, why applications get rejected.
4. **Doubts & Queries** — Technical skill guidance (which programming languages to learn, tools for specific sectors), soft skills, certifications worth doing.
5. **Platform Help** — How to apply for internships on InternConnect, understanding application status (pending/approved/rejected), chatting with mentors, using the resume analyzer.

Personality:
- Be warm, encouraging, and practical. Students are often anxious — reassure them.
- Give specific, actionable advice. Avoid vague answers.
- Use simple language. Avoid corporate jargon.
- If a student seems stressed, acknowledge it before giving advice.
- Format responses with bullet points or numbered lists when listing steps.
- Keep responses concise (3-5 sentences for simple questions, structured lists for complex ones).

Boundaries:
- Only answer questions related to careers, internships, applications, skills, and the InternConnect platform.
- If asked something unrelated (politics, entertainment, etc.), politely redirect: "I'm best at career and internship questions — happy to help with those!"
- Never make up internship listings or company-specific information you don't have.

Always end responses to first-time or stressed students with an encouraging note."""


# ─── GROQ CONFIG ─────────────────────────────────────────────────────────────
# Supported free Groq models (pick one):
#   - "llama-3.1-8b-instant"       ← fastest, great for chat
#   - "llama-3.3-70b-versatile"    ← smartest, slightly slower
#   - "mixtral-8x7b-32768"         ← excellent reasoning
#   - "gemma2-9b-it"               ← Google's model, very good

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')
GROQ_API_KEY = getattr(settings, 'GROQ_API_KEY', '')


def call_groq(messages_history: list, stream: bool = False) -> dict:
    """Call Groq API with conversation history."""
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages_history,
        "max_tokens": 1024,
        "temperature": 0.7,
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=30, stream=stream)
    response.raise_for_status()
    return response


# ─── VIEWS ───────────────────────────────────────────────────────────────────

@login_required
def chatbot_page(request):
    """Main chatbot UI page. Creates or retrieves session."""
    session_id = request.session.get('chatbot_session_id')
    session = None

    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id, student=request.user)
        except ChatSession.DoesNotExist:
            session = None

    if not session:
        session = ChatSession.objects.create(student=request.user)
        request.session['chatbot_session_id'] = session.id

    messages = session.messages.order_by('created_at')
    return render(request, 'student_portal/chatbot.html', {
        'session': session,
        'messages': messages,
        'student': request.user,
    })


@login_required
@require_POST
def chat_send(request):
    """AJAX: receive user message, call Groq, return AI response."""
    try:
        data = json.loads(request.body)
        user_input = data.get('message', '').strip()
        session_id = data.get('session_id')

        if not user_input:
            return JsonResponse({'error': 'Empty message'}, status=400)
        if len(user_input) > 2000:
            return JsonResponse({'error': 'Message too long (max 2000 chars)'}, status=400)

        session = get_object_or_404(ChatSession, id=session_id, student=request.user)

        # Save user message
        ChatMessage.objects.create(session=session, role='user', content=user_input)

        # Build history for LLM (last 16 messages = 8 turns)
        history = session.get_history_for_llm(limit=16)

        # Call Groq
        try:
            response = call_groq(history)
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            tokens = result.get('usage', {}).get('total_tokens', 0)
        except requests.exceptions.Timeout:
            ai_text = "Sorry, I'm taking too long to respond. Please try again in a moment."
            tokens = 0
        except requests.exceptions.RequestException as e:
            ai_text = "I'm having trouble connecting right now. Please try again shortly."
            tokens = 0
        except (KeyError, IndexError):
            ai_text = "Something went wrong on my end. Please try again."
            tokens = 0

        # Save AI response
        ChatMessage.objects.create(
            session=session, role='assistant', content=ai_text, tokens_used=tokens
        )
        session.save()  # bump updated_at

        return JsonResponse({
            'reply': ai_text,
            'session_id': session.id,
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Server error'}, status=500)


@login_required
@require_POST
def new_session(request):
    """Start a fresh chat session."""
    session = ChatSession.objects.create(student=request.user)
    request.session['chatbot_session_id'] = session.id
    return JsonResponse({'session_id': session.id})


@login_required
def session_history(request):
    """List all chat sessions for a student."""
    sessions = ChatSession.objects.filter(student=request.user).prefetch_related('messages')
    data = []
    for s in sessions:
        first_msg = s.messages.filter(role='user').first()
        data.append({
            'id': s.id,
            'started': s.started_at.strftime('%d %b %Y'),
            'preview': first_msg.content[:60] if first_msg else 'New conversation',
            'count': s.messages.count(),
        })
    return JsonResponse({'sessions': data})
