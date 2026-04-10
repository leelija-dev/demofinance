from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from agent.models import Agent
from loan.models import LoanApplication, EmiCollectionDetail
from django.contrib.auth.hashers import check_password
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
from agent.viewsapi import ChangePassword
import json
import logging

# Set up logging
logger = logging.getLogger(__name__)

class AgentDashboardView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'agent/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.request.session.get('agent_id')
        if agent_id:
            try:
                agent = Agent.objects.get(agent_id=agent_id)
                context['agent'] = agent
                context['submit_loan'] = LoanApplication.objects.filter(agent=agent).count()
                context['reject_loan'] = LoanApplication.objects.filter(agent=agent, status__in=['rejected_by_branch', 'hq_rejected']).count()
            except Agent.DoesNotExist:
                logger.error(f"Agent with ID {agent_id} not found in AgentDashboardView")
                context['agent'] = None
        return context

class AgentProfileView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'agent/profile.html'

class AgentLoginPageView(TemplateView):
    template_name = 'agent/login.html'

class AgentLoginAPI(APIView):
    def get(self, request):
        return render(request, 'agent/login.html')

    def post(self, request):
        email = request.data.get('username') or request.POST.get('username')
        password = request.data.get('password') or request.POST.get('password')
        error_msg = None
        try:
            agent = Agent.objects.get(email=email)
            if agent.status != 'active':
                error_msg = 'Your account is inactive. Please contact your branch.'
            elif check_password(password, agent.password_hash):
                request.session['agent_id'] = agent.agent_id
                if request.content_type.startswith('application/x-www-form-urlencoded') or request.content_type.startswith('multipart/form-data'):
                    return redirect('/agent/dashboard/')
                return Response({'success': True, 'message': 'Login successful', 'redirect': '/agent/dashboard/'})
            else:
                error_msg = 'Invalid credentials'
        except Agent.DoesNotExist:
            error_msg = 'Invalid credentials'
        if request.content_type.startswith('application/x-www-form-urlencoded') or request.content_type.startswith('multipart/form-data'):
            return render(request, 'agent/login.html', {'error': error_msg})
        return Response({'success': False, 'message': error_msg}, status=status.HTTP_401_UNAUTHORIZED)

class AgentLogoutView(View):
    def get(self, request):
        request.session.flush()
        return redirect('/agent/login/')

def change_password(request):
    if request.method == 'POST':
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return JsonResponse({'success': False, 'message': 'Not logged in.'}, status=401)

        mutable_post = request.POST.copy()
        new_password = mutable_post.get('new-password')
        confirm_password = mutable_post.get('confirm-password')

        mutable_post['agent_id'] = agent_id
        if new_password is not None:
            mutable_post['new_password'] = new_password
        if confirm_password is not None:
            mutable_post['confirm_password'] = confirm_password
        request._post = mutable_post

        api_response = ChangePassword.as_view()(request)
        if hasattr(api_response, 'render'):
            api_response.render()

        try:
            payload = json.loads(api_response.content)
        except (TypeError, ValueError):
            payload = {'message': 'Unable to process response from password service.'}

        success = api_response.status_code == 200
        payload.setdefault('success', success)

        return JsonResponse(payload, status=api_response.status_code)

    return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

def agent_info_api(request):
    agent_id = request.session.get('agent_id')
    if agent_id:
        try:
            agent = Agent.objects.select_related('branch').get(agent_id=agent_id, status='active')
        except Agent.DoesNotExist:
            logger.error(f"Agent with ID {agent_id} not found in agent_info_api")
            request.session.flush()
            return JsonResponse({'success': False, 'error': 'Not logged in'}, status=401)
        photo_url = agent.photo.url if agent.photo else None
        id_proof_url = agent.id_proof.url if agent.id_proof else None
        return JsonResponse({
            'success': True,
            'agent': {
                'agent_id': agent.agent_id,
                'full_name': agent.full_name,
                'email': agent.email,
                'phone': agent.phone,
                'role': agent.role,
                'area': agent.area,
                'status': agent.status,
                'created_at': agent.created_at,
                'updated_at': agent.updated_at,
                'created_by': getattr(agent.created_by, 'id', None),
                'photo_url': photo_url,
                'id_proof_url': id_proof_url,
            }
        })
    return JsonResponse({'success': False, 'error': 'Not logged in'}, status=401)

def agent_image_update_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    agent_id = request.session.get('agent_id')
    if not agent_id:
        return JsonResponse({'success': False, 'message': 'Not logged in.'}, status=401)

    photo_file = request.FILES.get('photo')
    if not photo_file:
        return JsonResponse({'success': False, 'message': 'No photo provided.'}, status=400)

    try:
        agent = Agent.objects.get(agent_id=agent_id, status='active')
    except Agent.DoesNotExist:
        request.session.flush()
        return JsonResponse({'success': False, 'message': 'Not logged in.'}, status=401)

    agent.photo = photo_file
    agent.save(update_fields=['photo'])

    photo_url = agent.photo.url if agent.photo else None

    return JsonResponse({
        'success': True,
        'message': 'Profile photo updated successfully.',
        'photo_url': photo_url,
        'agent': {
            'full_name': agent.full_name,
            'photo_url': photo_url,
        }
    })

class AgentDashboardStatsAPI(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            logger.error("No agent_id found in session")
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            agent = Agent.objects.get(agent_id=agent_id, status='active')
        except Agent.DoesNotExist:
            logger.error(f"Active agent with ID {agent_id} not found or inactive")
            request.session.flush()
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Time range handling
        rng = request.query_params.get('range', 'month')
        now = timezone.now()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        try:
            if rng == 'custom' and start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
                    end = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone(), hour=23, minute=59, second=59)
                    if start > end:
                        logger.error(f"Invalid date range: start {start} > end {end}")
                        return Response({'detail': 'End date cannot be before start date.'}, status=status.HTTP_400_BAD_REQUEST)
                    range_days = (end - start).days
                    trend_bins = min(10, max(1, range_days // 3))
                    bin_delta = timedelta(days=max(1, range_days / trend_bins))
                    label_fmt = '%d %b' if range_days > 7 else '%d %b, %H:%M'
                except ValueError as e:
                    logger.error(f"Invalid date format: start_date={start_date}, end_date={end_date}, error={str(e)}")
                    return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                if rng == 'day':
                    start = now - timedelta(days=1)
                    end = now
                    trend_bins = 24
                    bin_delta = timedelta(hours=1)
                    label_fmt = '%H'
                elif rng == 'week':
                    start = now - timedelta(days=7)
                    end = now
                    trend_bins = 7
                    bin_delta = timedelta(days=1)
                    label_fmt = '%d'
                else:  # month
                    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    end = now
                    trend_bins = 10
                    bin_delta = timedelta(days=(end - start).days / 10)
                    label_fmt = '%d'

            # Loan stats (strictly for the logged-in agent)
            try:
                loan_qs = LoanApplication.objects.filter(agent=agent, submitted_at__gte=start, submitted_at__lte=end)
                logger.info(f"Agent {agent.agent_id} loan count: {loan_qs.count()}")
            except Exception as e:
                logger.error(f"Error querying LoanApplication for agent {agent.agent_id}: {str(e)}")
                raise

            pending_statuses = ['pending', 'document_requested', 'resubmitted', 'rejected_by_branch', 'branch_document_accepted', 'branch_approved', 'branch_resubmitted', 'hq_resubmitted', 'hq_document_accepted', 'document_requested_by_hq', 'hq_approved']
            approved_statuses = ['branch_approved', 'hq_approved']
            disbursed_statuses = ['disbursed', 'disbursed_fund_released']
            rejected_statuses = ['reject', 'rejected_by_branch', 'hq_rejected']

            applied_count = loan_qs.count()
            pending_count = loan_qs.filter(status__in=pending_statuses).count()
            approved_count = loan_qs.filter(status__in=approved_statuses).count()
            disbursed_count = loan_qs.filter(status__in=disbursed_statuses).count()
            rejected_count = loan_qs.filter(status__in=rejected_statuses).count()

            stats = {
                'applied': applied_count,
                'pending': pending_count,
                'approved': approved_count,
                'disbursed': disbursed_count,
                'rejected': rejected_count,
            }

            # EMI totals (strictly for the logged-in agent)
            try:
                emi_qs = EmiCollectionDetail.objects.filter(collected_by_agent=agent, collected_at__gte=start, collected_at__lte=end)
                logger.info(f"Agent {agent.agent_id} EMI count: {emi_qs.count()}")
            except Exception as e:
                logger.error(f"Error querying EmiCollectionDetail for agent {agent.agent_id}: {str(e)}")
                raise

            emi_agg = emi_qs.aggregate(
                cnt=Count('collected_id'), amt=Sum('amount_received')
            )
            emi = {
                'count': emi_agg.get('cnt') or 0,
                'amount': float(emi_agg.get('amt') or 0) if emi_agg.get('amt') else 0.0
            }

            # Trends (agent-specific)
            trends = []
            bucket_start = start
            while bucket_start < end and len(trends) < trend_bins:
                bucket_end = min(bucket_start + bin_delta, end)
                cnt = loan_qs.filter(submitted_at__gte=bucket_start, submitted_at__lt=bucket_end).count()
                trends.append({
                    'label': bucket_start.astimezone(timezone.get_current_timezone()).strftime(label_fmt),
                    'count': cnt,
                })
                bucket_start = bucket_end

            # Distribution (agent-specific, zero if no data)
            distribution = [
                stats['applied'], stats['pending'], stats['approved'], stats['disbursed'], stats['rejected']
            ]

            # Recent activity (agent-specific)
            recent = []
            try:
                recent_emis = list(emi_qs.order_by('-collected_at')[:5])
                for r in recent_emis:
                    try:
                        customer_name = getattr(r.loan_application.customer, 'full_name', 'Customer')
                    except AttributeError as e:
                        logger.warning(f"Customer data missing for EMI {r.collected_id}: {str(e)}")
                        customer_name = 'Customer'
                    recent.append({
                        'id': r.collected_id,
                        'title': 'EMI Collected',
                        'subtitle': f"{customer_name} — ₹{r.amount_received}",
                        'time': r.collected_at.astimezone(timezone.get_current_timezone()).strftime('%d %b, %I:%M %p'),
                    })

                if len(recent) < 5:
                    recent_apps = list(loan_qs.order_by('-submitted_at')[: (5 - len(recent))])
                    for a in recent_apps:
                        try:
                            customer_name = getattr(a.customer, 'full_name', 'Customer')
                        except AttributeError as e:
                            logger.warning(f"Customer data missing for Loan {a.loan_ref_no}: {str(e)}")
                            customer_name = 'Customer'
                        recent.append({
                            'id': a.loan_ref_no,
                            'title': 'Loan Applied',
                            'subtitle': customer_name,
                            'time': a.submitted_at.astimezone(timezone.get_current_timezone()).strftime('%d %b, %I:%M %p'),
                        })
            except Exception as e:
                logger.error(f"Error processing recent activity for agent {agent.agent_id}: {str(e)}")
                raise

            # Log results to verify agent-specific data
            logger.info(f"Agent: {agent.agent_id}, Range: {rng}, Start: {start}, End: {end}, Distribution: {distribution}, Stats: {stats}, EMI: {emi}")

            return Response({
                'stats': stats,
                'emi': emi,
                'trends': trends,
                'distribution': distribution,
                'recent': recent,
            })

        except Exception as e:
            logger.error(f"Error in AgentDashboardStatsAPI for agent {agent_id}: {str(e)}", exc_info=True)
            return Response({'detail': f'Server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)