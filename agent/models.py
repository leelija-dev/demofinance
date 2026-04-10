from django.db import models
from django.conf import settings
from headquater.models import Branch
import os
import uuid
import re

def agent_photo_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    # Clean agent name for filesystem
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', instance.full_name) if instance.full_name else 'unknown'
    if instance.agent_id:
        new_filename = f"agent_{instance.agent_id}_{safe_name}.{ext}"
    else:
        import time
        new_filename = f"agent_new_{safe_name}_{int(time.time())}.{ext}"
    # Return path relative to MEDIA_ROOT (do NOT prefix with 'media/')
    return os.path.join('agent', 'agent_photo', new_filename)

def agent_id_proof_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', instance.full_name) if instance.full_name else 'unknown'
    if instance.agent_id:
        new_filename = f"agent_{instance.agent_id}_{safe_name}_idProof.{ext}"
    else:
        import time
        new_filename = f"agent_new_{safe_name}_{int(time.time())}_idProof.{ext}"
    # Return path relative to MEDIA_ROOT (do NOT prefix with 'media/')
    return os.path.join('agent', 'agent_idProof', new_filename)

class Agent(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    ROLE_CHOICES = [
        ('agent', 'Agent'),
    ]
    
    # Primary key - agent_id
    agent_id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    
    # Basic information
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=10, unique=True,)
    password_hash = models.TextField()  # Store hashed password
    
    # Branch relationship
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='agents')
    
    # Role and area
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    area = models.CharField(max_length=255)
    
    # File uploads
    id_proof = models.FileField(upload_to=agent_id_proof_upload_path)
    photo = models.ImageField(upload_to=agent_photo_upload_path, blank=True, null=True)
    
    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='agents_created'
    )
    
    class Meta:
        verbose_name = 'Agent'
        verbose_name_plural = 'Agents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.agent_id} - {self.full_name}"
    
    def get_full_name(self):
        return self.full_name
    
    def is_active(self):
        return self.status == 'active'
        
    def save(self, *args, **kwargs):
        # Generate agent_id if not set
        if not self.agent_id:
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.agent_id = f"AGENT-{short_uuid}"
        # If this is an update and we're changing the photo
        if self.pk and self.photo:
            try:
                old_instance = Agent.objects.get(pk=self.pk)
                # If there was an old photo and it's different from the new one
                if old_instance.photo and old_instance.photo.name != self.photo.name:
                    try:
                        if old_instance.photo.path and os.path.isfile(old_instance.photo.path):
                            os.remove(old_instance.photo.path)
                    except Exception:
                        pass
            except (Agent.DoesNotExist, ValueError, OSError):
                pass
        # If this is an update and we're changing the id_proof
        if self.pk and self.id_proof:
            try:
                old_instance = Agent.objects.get(pk=self.pk)
                if old_instance.id_proof and old_instance.id_proof.name != self.id_proof.name:
                    try:
                        if old_instance.id_proof.path and os.path.isfile(old_instance.id_proof.path):
                            os.remove(old_instance.id_proof.path)
                    except Exception:
                        pass
            except (Agent.DoesNotExist, ValueError, OSError):
                pass
        super().save(*args, **kwargs)
        # After save, rename the file if needed for new instances
        if self.photo and 'agent_new_' in self.photo.name:
            old_path = self.photo.path
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', self.full_name) if self.full_name else 'unknown'
            new_filename = f"agent_{self.agent_id}_{safe_name}.{self.photo.name.split('.')[-1]}"
            new_path = os.path.join(os.path.dirname(old_path), new_filename)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            self.photo.name = os.path.join('agent', 'agent_photo', new_filename)
            super().save(update_fields=['photo'])
        if self.id_proof and 'agent_new_' in self.id_proof.name:
            old_path = self.id_proof.path
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', self.full_name) if self.full_name else 'unknown'
            new_filename = f"agent_{self.agent_id}_{safe_name}_idProof.{self.id_proof.name.split('.')[-1]}"
            new_path = os.path.join(os.path.dirname(old_path), new_filename)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            self.id_proof.name = os.path.join('agent', 'agent_idProof', new_filename)
            super().save(update_fields=['id_proof'])
        