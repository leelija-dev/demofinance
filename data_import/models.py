"""
Models for data_import app
"""
from django.db import models

class ImportLog(models.Model):
    """Track import operations and their results"""
    
    IMPORT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    import_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    total_rows = models.PositiveIntegerField()
    successful_imports = models.PositiveIntegerField(default=0)
    failed_imports = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=IMPORT_STATUS_CHOICES, default='pending')
    error_summary = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'headquater.HeadquarterEmployee', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='import_logs'
    )
    
    class Meta:
        db_table = 'data_import_logs'
        ordering = ['-started_at']
        verbose_name = 'Import Log'
        verbose_name_plural = 'Import Logs'
    
    def __str__(self):
        return f"{self.import_id} - {self.file_name}"
    
    def save(self, *args, **kwargs):
        if not self.import_id:
            import uuid
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.import_id = f"IMPORT-{short_uuid}"
        super().save(*args, **kwargs)
    
    @property
    def success_rate(self):
        """Calculate success rate as percentage"""
        if self.total_rows == 0:
            return 0.0
        return round((self.successful_imports / self.total_rows) * 100, 2)

class ImportErrorDetail(models.Model):
    """Detailed error information for failed imports"""
    
    ERROR_TYPE_CHOICES = [
        ('validation', 'Validation Error'),
        ('reference', 'Reference Error'),
        ('processing', 'Processing Error'),
        ('system', 'System Error'),
    ]
    
    error_id = models.CharField(primary_key=True, max_length=50, editable=False, unique=True)
    import_log = models.ForeignKey(ImportLog, on_delete=models.CASCADE, related_name='error_details')
    row_number = models.PositiveIntegerField()
    field_name = models.CharField(max_length=100, blank=True, null=True)
    error_type = models.CharField(max_length=20, choices=ERROR_TYPE_CHOICES)
    error_message = models.TextField()
    error_data = models.JSONField(default=dict, blank=True, help_text="Original row data that caused the error")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_import_error_details'
        ordering = ['row_number']
        verbose_name = 'Import Error Detail'
        verbose_name_plural = 'Import Error Details'
        indexes = [
            models.Index(fields=['import_log', 'row_number']),
            models.Index(fields=['error_type']),
        ]
    
    def __str__(self):
        return f"Error {self.error_id} - Row {self.row_number}"
    
    def save(self, *args, **kwargs):
        if not self.error_id:
            import uuid
            short_uuid = str(uuid.uuid4())[:8].upper()
            self.error_id = f"ERR-{short_uuid}"
        super().save(*args, **kwargs)
