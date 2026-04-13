from django.urls import path
from . import views

app_name = 'data_import'

urlpatterns = [
    path('upload-excel/', views.upload_excel, name='upload_excel'),
    path('process-data/', views.process_excel_data, name='process_excel_data'),
]
