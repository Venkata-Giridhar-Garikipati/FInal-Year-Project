from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.mentor_login, name='mentor_login'),
    path('logout/', views.mentor_logout, name='mentor_logout'),
    path('dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    path('create-internship/', views.create_internship, name='create_internship'),
    path('applications/', views.view_applications, name='view_applications'),
    path('applications/update/<int:pk>/', views.update_application, name='update_application'),
    path('create-class/', views.create_class, name='create_class'),


    # Mentor
    path('students/', views.mentor_student_list, name='mentor_student_list'),
    path('students/<int:student_id>/', views.mentor_chat, name='mentor_chat'),

    # Shared AJAX
    path('send/', views.send_message, name='send_message'),
    path('poll/<int:other_user_id>/', views.poll_messages, name='poll_messages'),


]