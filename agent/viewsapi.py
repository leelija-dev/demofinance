from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from agent.models import Agent
from loan.models import LoanApplication, EmiCollectionDetail
from django.contrib.auth.hashers import check_password, make_password
from django.views import View
from agent.decorators import AgentSessionRequiredMixin
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Sum, Q
import logging

# Set up logging
logger = logging.getLogger(__name__)

class ChangePassword(APIView):
    def post(self, request):
        agent_id = request.data.get('agent_id')

        if not agent_id:
            return Response({'message': 'Agent ID Not Found!.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'message': 'Agent Not !Found.'}, status=status.HTTP_404_NOT_FOUND)

        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not new_password or not confirm_password:
            return Response({'message': 'New Password and Confirm Password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'message': 'New Password and Confirm Password do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        agent.password_hash = make_password(new_password)
        agent.save()

        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)