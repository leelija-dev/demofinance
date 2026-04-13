"""
Django app configuration for data_import module
"""
from django.apps import AppConfig


class DataImportConfig(AppConfig):
    default_auto_field = 'id'
    name = 'data_import'
    verbose_name = 'Data Import'
    
    def ready(self):
        """Initialize app when Django starts"""
        # Import signals if needed
        # from . import signals
        pass
