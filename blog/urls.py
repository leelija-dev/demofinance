from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Admin CRUD views - Super Admin only (must come before generic slug patterns)
    path('admin/', views.blog_admin_list, name='admin_list'),
    path('admin/create/', views.blog_create, name='create'),
    path('admin/edit/<slug:slug>/', views.blog_edit, name='edit'),
    path('admin/delete/<slug:slug>/', views.blog_delete, name='delete'),
    path('admin/category/create/', views.category_create, name='category_create'),
    path('admin/tag/create/', views.tag_create, name='tag_create'),
    path('admin/faq/<int:faq_id>/delete/', views.faq_delete, name='faq_delete'),
    
    # Public views
    path('', views.blog_list, name='list'),
    path('category/<slug:slug>/', views.category_blogs, name='category'),
    path('tag/<slug:slug>/', views.tag_blogs, name='tag'),
    path('<slug:slug>/', views.blog_detail, name='detail'),
]