from django import forms
from django.core.exceptions import ValidationError
from .models import Blog, Category, Tag, FAQ
from django_ckeditor_5.widgets import CKEditor5Widget
from django.forms import inlineformset_factory


class BlogForm(forms.ModelForm):
    """Form for creating and editing blog posts with enhanced validation"""
    
    class Meta:
        model = Blog
        fields = ['title', 'slug', 'category', 'tags', 'featured_image', 'excerpt', 'content', 'status', 'featured']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Enter an engaging title for your blog post',
                'maxlength': 255
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Leave blank to auto-generate from title',
                'maxlength': 280
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200'
            }),
            'tags': forms.CheckboxSelectMultiple(),
            'excerpt': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200 resize-none',
                'rows': 3,
                'placeholder': 'Write a short excerpt for the blog listing'
            }),
            'content': CKEditor5Widget(config_name='default'),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200'
            }),
            'featured': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-blue-600 rounded border-gray-300 focus:ring-blue-500'
            }),
            'featured_image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = "Select Category"
        self.fields['category'].required = False
        self.fields['tags'].required = False
        self.fields['featured_image'].required = False
        self.fields['slug'].required = False  # Make optional since we auto-generate
        
        # Add help text and custom attributes
        self.fields['title'].help_text = "Required: 3-255 characters"
        self.fields['content'].help_text = "Required: Minimum 10 characters"
        self.fields['status'].help_text = "Required: Choose draft or published status"
        self.fields['slug'].help_text = "Optional: Leave blank to auto-generate from title, or enter custom URL slug"
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title:
            if len(title) < 3:
                raise ValidationError("Title must be at least 3 characters long.")
            if len(title) > 255:
                raise ValidationError("Title cannot exceed 255 characters.")
        return title
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content:
            if len(content) < 10:
                raise ValidationError("Content must be at least 10 characters long.")
        return content
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        title = self.cleaned_data.get('title')
        
        # Auto-generate slug if not provided
        if not slug and title:
            from django.utils.text import slugify
            slug = slugify(title)
        
        if slug:
            # Additional slug validation
            if not slug.replace('-', '').isalnum():
                raise ValidationError("Slug can only contain alphanumeric characters and hyphens.")
            
            # Check for uniqueness (excluding current instance if editing)
            blog_id = self.instance.id if self.instance.id else None
            existing_blogs = Blog.objects.filter(slug=slug)
            if blog_id:
                existing_blogs = existing_blogs.exclude(id=blog_id)
            
            if existing_blogs.exists():
                raise ValidationError("A blog post with this slug already exists. Please choose a different slug.")
        
        return slug
    
    def clean_featured_image(self):
        image = self.cleaned_data.get('featured_image')
        if image:
            # Validate file size (max 5MB)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError("Image file size cannot exceed 5MB.")
            
            # Validate file type
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            import os
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError("Only JPG, PNG, WEBP, and GIF image formats are allowed.")
        return image


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories with enhanced validation"""
    
    class Meta:
        model = Category
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Enter category name',
                'maxlength': 100
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Leave blank to auto-generate from name',
                'maxlength': 120
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].help_text = "Required: 2-100 characters"
        self.fields['slug'].help_text = "Optional: Leave blank to auto-generate from name, or enter custom URL slug"
        self.fields['slug'].required = False  # Make optional since we auto-generate
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            if len(name) < 2:
                raise ValidationError("Category name must be at least 2 characters long.")
            if len(name) > 100:
                raise ValidationError("Category name cannot exceed 100 characters.")
        return name
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        
        # Auto-generate slug if not provided
        if not slug and name:
            from django.utils.text import slugify
            slug = slugify(name)
        
        if slug:
            # Additional slug validation
            if not slug.replace('-', '').isalnum():
                raise ValidationError("Slug can only contain alphanumeric characters and hyphens.")
            
            # Check for uniqueness (excluding current instance if editing)
            category_id = self.instance.id if self.instance.id else None
            existing_categories = Category.objects.filter(slug=slug)
            if category_id:
                existing_categories = existing_categories.exclude(id=category_id)
            
            if existing_categories.exists():
                raise ValidationError("A category with this slug already exists. Please choose a different slug.")
        
        return slug
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        slug = cleaned_data.get('slug')
        
        # Ensure we have either a slug or can generate one from name
        if not slug and not name:
            raise ValidationError("Either provide a category name or a slug.")
        
        return cleaned_data


class TagForm(forms.ModelForm):
    """Form for creating and editing tags with enhanced validation"""
    
    class Meta:
        model = Tag
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Enter tag name',
                'maxlength': 50
            }),
            'slug': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Leave blank to auto-generate from name',
                'maxlength': 60
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].help_text = "Required: 2-50 characters"
        self.fields['slug'].help_text = "Optional: Leave blank to auto-generate from name, or enter custom URL slug"
        self.fields['slug'].required = False  # Make optional since we auto-generate
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            if len(name) < 2:
                raise ValidationError("Tag name must be at least 2 characters long.")
            if len(name) > 50:
                raise ValidationError("Tag name cannot exceed 50 characters.")
        return name
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        
        # Auto-generate slug if not provided
        if not slug and name:
            from django.utils.text import slugify
            slug = slugify(name)
        
        if slug:
            # Additional slug validation
            if not slug.replace('-', '').isalnum():
                raise ValidationError("Slug can only contain alphanumeric characters and hyphens.")
            
            # Check for uniqueness (excluding current instance if editing)
            tag_id = self.instance.id if self.instance.id else None
            existing_tags = Tag.objects.filter(slug=slug)
            if tag_id:
                existing_tags = existing_tags.exclude(id=tag_id)
            
            if existing_tags.exists():
                raise ValidationError("A tag with this slug already exists. Please choose a different slug.")
        
        return slug
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        slug = cleaned_data.get('slug')
        
        # Ensure we have either a slug or can generate one from name
        if not slug and not name:
            raise ValidationError("Either provide a tag name or a slug.")
        
        return cleaned_data


class FAQForm(forms.ModelForm):
    """Form for creating and editing FAQs"""
    
    class Meta:
        model = FAQ
        fields = ['question', 'answer', 'order']
        widgets = {
            'question': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200',
                'placeholder': 'Enter your question',
                'maxlength': 255
            }),
            'answer': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white transition-all duration-200 resize-none',
                'rows': 3,
                'placeholder': 'Enter the answer to the question'
            }),
            'order': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['question'].help_text = "Required: 1-255 characters"
        self.fields['answer'].help_text = "Required: Minimum 2 characters"
    
    def clean_question(self):
        question = self.cleaned_data.get('question')
        if question:
            if len(question) < 1:
                raise ValidationError("Question must be at least 1 character long.")
            if len(question) > 255:
                raise ValidationError("Question cannot exceed 255 characters.")
        return question
    
    def clean_answer(self):
        answer = self.cleaned_data.get('answer')
        if answer:
            if len(answer) < 2:
                raise ValidationError("Answer must be at least 2 characters long.")
        return answer


# Create an inline formset for FAQs to be used with BlogForm
FAQFormSet = inlineformset_factory(
    Blog,
    FAQ,
    form=FAQForm,
    extra=1,  # Number of empty forms to display
    can_delete=True,  # Allow deletion of FAQs
    min_num=0,  # Minimum number of forms
    max_num=20,  # Maximum number of FAQs per blog post
    validate_min=True,
    validate_max=True
)