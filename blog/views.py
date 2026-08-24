from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Blog, Category, Tag, FAQ
from .forms import BlogForm, CategoryForm, TagForm, FAQFormSet
from headquater.decorators import require_super_admin


def blog_list(request):
    """Display all published blog posts"""
    # Get search query
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    
    # Start with published blogs ordered by most recent first
    blogs = Blog.objects.filter(status=Blog.Status.PUBLISHED).select_related(
        'author', 'category'
    ).prefetch_related('tags').order_by('-published_at', '-created_at')
    
    # Apply search filter
    if search_query:
        blogs = blogs.filter(
            title__icontains=search_query
        )
    
    # Apply category filter
    if category_filter:
        blogs = blogs.filter(category__slug=category_filter)
    
    # Get featured post (most recent featured post) - only show featured when no filters are applied
    featured_post = None
    if not search_query and not category_filter:
        featured_post = blogs.filter(featured=True).first()
    
    # Always show all blogs in the main grid (including featured if it exists)
    # This ensures that even if there's only one article, it will be shown
    regular_blogs = blogs
    
    categories = Category.objects.all()
    tags = Tag.objects.all()
    
    context = {
        'blogs': regular_blogs,
        'featured_post': featured_post,
        'categories': categories,
        'tags': tags,
        'search_query': search_query,
        'category_filter': category_filter,
    }
    return render(request, 'blog/blog_list.html', context)


def blog_detail(request, slug):
    """Display a single blog post"""
    blog = get_object_or_404(Blog, slug=slug, status=Blog.Status.PUBLISHED)
    
    # Increment view count
    blog.views += 1
    blog.save(update_fields=['views'])
    
    # Get related posts (same category, excluding current post)
    related_posts = Blog.objects.filter(
        status=Blog.Status.PUBLISHED,
        category=blog.category
    ).exclude(id=blog.id)[:3]
    
    # Get FAQs for this blog post
    faqs = blog.faqs.all().order_by('order', 'created_at')
    
    context = {
        'blog': blog,
        'related_posts': related_posts,
        'faqs': faqs,
    }
    return render(request, 'blog/blog_detail.html', context)


def category_blogs(request, slug):
    """Display blogs for a specific category"""
    category = get_object_or_404(Category, slug=slug)
    blogs = Blog.objects.filter(
        status=Blog.Status.PUBLISHED,
        category=category
    ).select_related('author', 'category')
    
    context = {
        'category': category,
        'blogs': blogs,
    }
    return render(request, 'blog/category_blogs.html', context)


def tag_blogs(request, slug):
    """Display blogs for a specific tag"""
    tag = get_object_or_404(Tag, slug=slug)
    blogs = Blog.objects.filter(
        status=Blog.Status.PUBLISHED,
        tags=tag
    ).select_related('author', 'category').prefetch_related('tags')
    
    context = {
        'tag': tag,
        'blogs': blogs,
    }
    return render(request, 'blog/tag_blogs.html', context)


# Admin CRUD Views - Only Super Admin Access

@require_super_admin
def blog_create(request):
    """Create a new blog post - Super Admin only"""
    if request.method == 'POST':
        form = BlogForm(request.POST, request.FILES)
        faq_formset = FAQFormSet(request.POST)
        
        if form.is_valid() and faq_formset.is_valid():
            blog = form.save(commit=False)
            blog.author = request.user
            # Auto-generate slug if not provided (already handled in form clean_slug)
            # Set published_at if status is published
            if blog.status == Blog.Status.PUBLISHED and not blog.published_at:
                from django.utils import timezone
                blog.published_at = timezone.now()
            
            blog.save()
            form.save_m2m()  # Save many-to-many relationships
            
            # Save FAQs
            faq_formset.instance = blog
            faqs = faq_formset.save(commit=False)
            
            # Set order based on form values (managed by JavaScript drag-and-drop)
            for faq in faqs:
                if faq.order is None:
                    # Fallback to index if order is not set
                    faq.order = 0
                faq.save()
            
            # Handle deleted FAQs
            for obj in faq_formset.deleted_objects:
                obj.delete()
            
            messages.success(request, 'Blog post created successfully!')
            return redirect('blog:list')
        else:
            # Debug: print formset errors if any
            if not faq_formset.is_valid():
                for form in faq_formset:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'FAQ {field} error: {error}')
                if faq_formset.non_form_errors():
                    for error in faq_formset.non_form_errors():
                        messages.error(request, f'FAQ formset error: {error}')
    else:
        form = BlogForm()
        faq_formset = FAQFormSet()
    
    context = {
        'form': form,
        'faq_formset': faq_formset,
        'title': 'Create New Blog Post',
        'categories': Category.objects.all(),
        'tags': Tag.objects.all(),
    }
    return render(request, 'blog/blog_form.html', context)


@require_super_admin
def blog_edit(request, slug):
    """Edit an existing blog post - Super Admin only"""
    blog = get_object_or_404(Blog, slug=slug)
    
    if request.method == 'POST':
        form = BlogForm(request.POST, request.FILES, instance=blog)
        faq_formset = FAQFormSet(request.POST, instance=blog)
        
        if form.is_valid() and faq_formset.is_valid():
            updated_blog = form.save(commit=False)
            
            # Update published_at if status changed to published
            if blog.status != Blog.Status.PUBLISHED and updated_blog.status == Blog.Status.PUBLISHED:
                from django.utils import timezone
                updated_blog.published_at = timezone.now()
            
            updated_blog.save()
            form.save_m2m()
            
            # Save FAQs
            faqs = faq_formset.save(commit=False)
            
            # Set order based on form values (managed by JavaScript drag-and-drop)
            for faq in faqs:
                if faq.order is None:
                    # Fallback to index if order is not set
                    faq.order = 0
                faq.save()
            
            # Handle deleted FAQs
            for obj in faq_formset.deleted_objects:
                obj.delete()
            
            messages.success(request, 'Blog post updated successfully!')
            return redirect('blog:admin_list')
        else:
            # Debug: print formset errors if any
            if not faq_formset.is_valid():
                for form in faq_formset:
                    for field, errors in form.errors.items():
                        for error in errors:
                            messages.error(request, f'FAQ {field} error: {error}')
                if faq_formset.non_form_errors():
                    for error in faq_formset.non_form_errors():
                        messages.error(request, f'FAQ formset error: {error}')
    else:
        form = BlogForm(instance=blog)
        faq_formset = FAQFormSet(instance=blog)
    
    context = {
        'form': form,
        'faq_formset': faq_formset,
        'blog': blog,
        'title': 'Edit Blog Post',
        'categories': Category.objects.all(),
        'tags': Tag.objects.all(),
    }
    return render(request, 'blog/blog_form.html', context)


@require_super_admin
def blog_delete(request, slug):
    """Delete a blog post - Super Admin only"""
    blog = get_object_or_404(Blog, slug=slug)
    
    if request.method == 'POST':
        blog.delete()
        messages.success(request, 'Blog post deleted successfully!')
        return redirect('blog:list')
    
    context = {
        'blog': blog,
        'title': 'Delete Blog Post',
    }
    return render(request, 'blog/blog_confirm_delete.html', context)


@require_super_admin
def blog_admin_list(request):
    """List all blog posts for admin management - Super Admin only"""
    blogs = Blog.objects.all().select_related('author', 'category').prefetch_related('tags')
    
    # Calculate statistics
    total_posts = blogs.count()
    published_posts = blogs.filter(status=Blog.Status.PUBLISHED).count()
    draft_posts = blogs.filter(status=Blog.Status.DRAFT).count()
    total_views = sum(blog.views for blog in blogs)
    
    context = {
        'blogs': blogs,
        'title': 'Manage Blog Posts',
        'total_posts': total_posts,
        'published_posts': published_posts,
        'draft_posts': draft_posts,
        'total_views': total_views,
    }
    return render(request, 'blog/blog_admin_list.html', context)


@require_super_admin
def category_create(request):
    """Create a new category - Super Admin only"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            # Auto-generate slug if not provided (already handled in form clean_slug)
            category.save()
            messages.success(request, 'Category created successfully!')
            return redirect('blog:admin_list')
        else:
            # If form is not valid, the errors will be displayed in the template
            pass
    else:
        form = CategoryForm()
    
    context = {
        'form': form,
        'title': 'Create New Category',
    }
    return render(request, 'blog/category_form.html', context)


@require_super_admin
def tag_create(request):
    """Create a new tag - Super Admin only"""
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            tag = form.save(commit=False)
            # Auto-generate slug if not provided (already handled in form clean_slug)
            tag.save()
            messages.success(request, 'Tag created successfully!')
            return redirect('blog:admin_list')
        else:
            # If form is not valid, the errors will be displayed in the template
            pass
    else:
        form = TagForm()
    
    context = {
        'form': form,
        'title': 'Create New Tag',
    }
    return render(request, 'blog/tag_form.html', context)


@require_super_admin
@csrf_exempt
def faq_delete(request, faq_id):
    """Delete a single FAQ via AJAX - Super Admin only"""
    if request.method == 'POST':
        try:
            faq = get_object_or_404(FAQ, id=faq_id)
            faq.delete()
            return JsonResponse({'success': True, 'message': 'FAQ deleted successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
