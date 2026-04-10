from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from .models import BranchEmployee, BranchTransaction, BranchRole, AgentDeposit, AgentDepositDenomination,BranchAccount
from headquater.models import Branch, HeadquartersWallet, HeadquartersTransactions, FundTransfers
# from .decorators import branch_manager_required
from agent.models import Agent
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib import messages
from .serializers import AgentSerializer
from loan.models import LoanApplication, CustomerDetail, DocumentReupload, DocumentReview, LoanPeriod, LoanEMISchedule, EmiAgentAssign, EmiCollectionDetail, LoanCloseRequest, ChartOfAccount
from loan.serializers import LoanApplicationListSerializer, CustomerLoanDetailSerializer, CustomerAddressSerializer, DocumentRequestSerializer, LoanDisbursedListSerializer, LoanEMIScheduleSerializer, CustomerAccountSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings


# for generated pdf report of fund release#
import asyncio
from playwright.async_api import async_playwright
import subprocess
import sys

from django.db.models.functions import TruncMonth, TruncYear, TruncDay
from django.db.models import Count, Sum

# Create your views here.

class ChangePassword(APIView):
    def post(self, request):
        logged_user_id = request.data.get('logged_user_id')

        if not logged_user_id:
            return Response({'message': 'Employee ID Not Found!.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            employee = BranchEmployee.objects.get(id=logged_user_id)
        except Agent.DoesNotExist:
            return Response({'message': 'Employee Not !Found.'}, status=status.HTTP_404_NOT_FOUND)

        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not new_password or not confirm_password:
            return Response({'message': 'New Password and Confirm Password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({'message': 'New Password and Confirm Password do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        employee.password_hash = make_password(new_password)
        employee.save()

        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)