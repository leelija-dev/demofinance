from django.conf import settings
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:category", kwargs={"slug": self.slug})


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:tag", kwargs={"slug": self.slug})


class Blog(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=255)

    slug = models.SlugField(
        max_length=280,
        unique=True,
        blank=True
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts"
    )

    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="posts"
    )

    featured_image = models.ImageField(
        upload_to="blog/images/",
        blank=True,
        null=True
    )

    excerpt = models.TextField(
        blank=True,
        help_text="Short description of the blog post."
    )

    content = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    featured = models.BooleanField(
        default=False
    )

    views = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "blog:detail",
            kwargs={"slug": self.slug}
        )

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED


class FAQ(models.Model):
    """FAQ model for blog posts - allows multiple FAQs per blog post"""
    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="faqs"
    )
    question = models.CharField(
        max_length=255,
        help_text="The FAQ question"
    )
    answer = models.TextField(
        help_text="The FAQ answer"
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Order in which the FAQ should appear"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question