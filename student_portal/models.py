from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, role='student'):
        if not email:
            raise ValueError('Email required')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, role=role)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None):
        user = self.create_user(email, full_name, password, role='admin')
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (('student', 'Student'), ('mentor', 'Mentor'), ('admin', 'Admin'))
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    objects = CustomUserManager()

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class Feedback(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feedbacks')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.student.full_name}"


class Application(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='applications')
    internship = models.ForeignKey('mentor_portal.Internship', on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mentor_feedback = models.TextField(blank=True, null=True)
    status_message = models.TextField(blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'internship')

    def __str__(self):
        return f"{self.student.full_name} → {self.internship.title} [{self.status}]"


class PredictionResult(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='predictions')
    resume_filename = models.CharField(max_length=255)
    predicted_category = models.CharField(max_length=150)
    confidence_score = models.FloatField(null=True, blank=True)
    top_categories = models.JSONField(default=list)
    top_jobs = models.JSONField(default=list)
    matched_internships = models.JSONField(default=list)
    words_extracted = models.PositiveIntegerField(default=0)
    raw_text_preview = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.full_name} — {self.predicted_category} ({self.created_at.date()})"
    

from django.db import models
from student_portal.models import CustomUser


class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.full_name} → {self.receiver.full_name}: {self.content[:40]}"

    @classmethod
    def get_conversation(cls, user1, user2):
        return cls.objects.filter(
            models.Q(sender=user1, receiver=user2) |
            models.Q(sender=user2, receiver=user1)
        ).order_by('created_at')

    @classmethod
    def unread_count(cls, receiver, sender):
        return cls.objects.filter(sender=sender, receiver=receiver, is_read=False).count()

    @classmethod
    def mark_as_read(cls, receiver, sender):
        cls.objects.filter(sender=sender, receiver=receiver, is_read=False).update(is_read=True)

from django.db import models
from student_portal.models import CustomUser


class ChatSession(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Session — {self.student.full_name} ({self.started_at.strftime('%d %b %Y %H:%M')})"

    def get_history_for_llm(self, limit=20):
        """Return last N messages in Groq/OpenAI format."""
        messages = self.messages.order_by('-created_at')[:limit]
        history = []
        for msg in reversed(messages):
            history.append({"role": msg.role, "content": msg.content})
        return history


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    tokens_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role.upper()}] {self.content[:60]}"
