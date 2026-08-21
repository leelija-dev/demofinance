from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from .models import Blog, Category, Tag
from .forms import BlogForm, CategoryForm, TagForm
from headquater.decorators import require_super_admin


def blog_list(request):
    """Display all published blog posts"""
    blogs = Blog.objects.filter(status=Blog.Status.PUBLISHED).select_related(
        'author', 'category'
    ).prefetch_related('tags')
    
    categories = Category.objects.all()
    tags = Tag.objects.all()
    
    context = {
        'blogs': blogs,
        'categories': categories,
        'tags': tags,
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
    
    context = {
        'blog': blog,
        'related_posts': related_posts,
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
        if form.is_valid():
            blog = form.save(commit=False)
            blog.author = request.user
            # Auto-generate slug if not provided (already handled in form clean_slug)
            # Set published_at if status is published
            if blog.status == Blog.Status.PUBLISHED and not blog.published_at:
                from django.utils import timezone
                blog.published_at = timezone.now()
            
            blog.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, 'Blog post created successfully!')
            return redirect('blog:list')
        else:
            # If form is not valid, the errors will be displayed in the template
            pass
    else:
        form = BlogForm()
    
    context = {
        'form': form,
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
        if form.is_valid():
            updated_blog = form.save(commit=False)
            
            # Update published_at if status changed to published
            if blog.status != Blog.Status.PUBLISHED and updated_blog.status == Blog.Status.PUBLISHED:
                from django.utils import timezone
                updated_blog.published_at = timezone.now()
            
            updated_blog.save()
            form.save_m2m()
            messages.success(request, 'Blog post updated successfully!')
            return redirect('blog:detail', slug=updated_blog.slug)
        else:
            # If form is not valid, the errors will be displayed in the template
            pass
    else:
        form = BlogForm(instance=blog)
    
    context = {
        'form': form,
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
