"""
Serializers for data_import module
"""
from rest_framework import serializers
from django.core.exceptions import ValidationError

class ExcelUploadSerializer(serializers.Serializer):
    """Serializer for Excel file upload API"""
    excel_file = serializers.FileField()
    skip_duplicates = serializers.BooleanField(default=True)
    update_existing = serializers.BooleanField(default=False)
    validate_references = serializers.BooleanField(default=True)
    batch_size = serializers.IntegerField(default=100, min_value=1, max_value=1000)
    continue_on_error = serializers.BooleanField(default=True)

class ImportResultSerializer(serializers.Serializer):
    """Serializer for import results"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    successful_imports = serializers.IntegerField()
    failed_imports = serializers.IntegerField()
    error_details = serializers.ListField(child=serializers.CharField())
    has_more_errors = serializers.BooleanField()
    total_records = serializers.IntegerField()
    success_rate = serializers.FloatField()

class ValidationErrorSerializer(serializers.Serializer):
    """Serializer for validation errors"""
    row_number = serializers.IntegerField()
    field = serializers.CharField()
    error_message = serializers.CharField()
    value = serializers.CharField(allow_null=True)

class ImportProgressSerializer(serializers.Serializer):
    """Serializer for import progress tracking"""
    total_records = serializers.IntegerField()
    processed_records = serializers.IntegerField()
    successful_imports = serializers.IntegerField()
    failed_imports = serializers.IntegerField()
    current_row = serializers.IntegerField()
    percentage_complete = serializers.FloatField()
    status = serializers.CharField()
    estimated_time_remaining = serializers.IntegerField(allow_null=True)
