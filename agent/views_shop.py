from django.views.generic import TemplateView
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from agent.decorators import AgentSessionRequiredMixin
from loan.models import Shop, ShopBankAccount
from agent.models import Agent
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.utils import DataError
import json
import logging

logger = logging.getLogger(__name__)


class ShopLoansAPI(AgentSessionRequiredMixin, APIView):
    """API to get loan applications for a specific shop (for logged-in agent)."""

    def get(self, request, *args, **kwargs):
        shop_id = request.GET.get('shop_id', '').strip()
        if not shop_id:
            return Response({'success': False, 'message': 'Shop ID is required.'}, status=400)

        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
            shop = Shop.objects.get(shop_id=shop_id, agent=agent)

            from loan.models import LoanApplication

            loans_qs = (
                LoanApplication.objects
                .filter(shop=shop)
                .select_related('customer')
                .prefetch_related('loan_details')
                .order_by('-submitted_at')
            )

            loans_data = []
            for loan in loans_qs:
                loan_detail = loan.loan_details.first() if hasattr(loan, 'loan_details') else None
                loans_data.append({
                    'loan_ref_no': loan.loan_ref_no,
                    'customer_name': loan.customer.full_name if loan.customer else 'N/A',
                    'status': loan.status,
                    'submitted_at': loan.submitted_at.isoformat() if loan.submitted_at else None,
                    'loan_amount': str(getattr(loan_detail, 'loan_amount', '') or ''),
                    'emi_amount': str(getattr(loan_detail, 'emi_amount', '') or ''),
                })

            return Response({
                'success': True,
                'shop_id': shop.shop_id,
                'shop_name': shop.name,
                'loans': loans_data,
            }, status=200)

        except Agent.DoesNotExist:
            return Response({'success': False, 'message': 'Agent not found.'}, status=404)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching shop loans: {str(e)}")
            return Response({'success': False, 'message': 'Failed to fetch shop loans. Please try again.'}, status=500)


class ShopTransactionsAPI(AgentSessionRequiredMixin, APIView):
    """API to get disbursement-related transactions for a specific shop (for logged-in agent)."""

    def get(self, request, *args, **kwargs):
        shop_id = request.GET.get('shop_id', '').strip()
        if not shop_id:
            return Response({'success': False, 'message': 'Shop ID is required.'}, status=400)

        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
            shop = Shop.objects.get(shop_id=shop_id, agent=agent)

            from branch.models import BranchTransaction

            from django.db.models import Q
            tx_qs = (
                BranchTransaction.objects
                .select_related('branch_account', 'disbursement_log', 'disbursement_log__loan_id')
                .filter((Q(disbursement_log__loan_id__shop=shop) | Q(shop=shop)))
                .order_by('-transaction_date')
            )

            tx_data = []
            for tx in tx_qs:
                loan = getattr(getattr(tx, 'disbursement_log', None), 'loan_id', None)
                tx_data.append({
                    'transaction_id': tx.transaction_id,
                    'transaction_type': tx.transaction_type,
                    'amount': str(tx.amount) if tx.amount is not None else '',
                    'purpose': tx.purpose,
                    'code': tx.code,
                    'mode': tx.mode,
                    'bank_payment_method': tx.bank_payment_method,
                    'transfer_to_from': tx.transfer_to_from,
                    'description': tx.description,
                    'transaction_date': tx.transaction_date.isoformat() if tx.transaction_date else None,
                    'loan_ref_no': getattr(loan, 'loan_ref_no', None),
                    'branch_account': {
                        'id': tx.branch_account.id,
                        'bank_name': tx.branch_account.bank_name,
                        'account_number': tx.branch_account.account_number,
                    } if tx.branch_account else None,
                })

            return Response({
                'success': True,
                'shop_id': shop.shop_id,
                'shop_name': shop.name,
                'transactions': tx_data,
            }, status=200)

        except Agent.DoesNotExist:
            return Response({'success': False, 'message': 'Agent not found.'}, status=404)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching shop transactions: {str(e)}")
            return Response({'success': False, 'message': 'Failed to fetch shop transactions. Please try again.'}, status=500)


class ShopView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'shop/shop.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Shop'
        
        # Get agent from session
        agent_id = self.request.session.get('agent_id')
        
        # Check if we should show active shops (switch ON = show active, switch OFF = show inactive)
        # Default is True (show active shops)
        show_active = self.request.GET.get('show_active', 'true') == 'true'
        
        if agent_id:
            # Check if agent exists
            try:
                agent = Agent.objects.get(agent_id=agent_id)
            except Agent.DoesNotExist:
                context['shops'] = []
                context['categories'] = []
                context['show_active'] = show_active
                return context
            
            # Get shops for the agent, showing active when switch is ON, inactive when switch is OFF
            if show_active:
                shops_qs = Shop.objects.filter(agent__agent_id=agent_id).exclude(status='inactive').order_by('-created_at')
            else:
                shops_qs = Shop.objects.filter(agent__agent_id=agent_id, status='inactive').order_by('-created_at')
            
            context['shops'] = shops_qs
            context['show_active'] = show_active
            
            # Get unique categories for the filter dropdown
            categories = list(shops_qs.values_list('category', flat=True).distinct().exclude(category__isnull=True).exclude(category=''))
            context['categories'] = categories
        else:
            context['shops'] = []
            context['categories'] = []
            context['show_active'] = show_active
            
        return context


class ShopListPagePartialView(AgentSessionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        page = request.GET.get('page') or 1

        # Get actual shops from database for the logged-in agent
        agent_id = request.session.get('agent_id')
        if agent_id:
            shops_qs = Shop.objects.filter(agent__agent_id=agent_id).order_by('-created_at')
        else:
            # If no agent in session, return empty
            shops_qs = Shop.objects.none()

        paginator = Paginator(shops_qs, 10)
        page_obj = paginator.get_page(page)
        shops = list(page_obj.object_list)

        if not shops:
            return HttpResponse('', content_type='text/html')

        # Generate HTML rows directly
        html_rows = []
        for shop in shops:
            status_badge = ""
            if shop.status == 'active':
                status_badge = f'<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">{shop.status.title()}</span>'
            elif shop.status == 'pending':
                status_badge = f'<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">{shop.status.title()}</span>'
            else:
                status_badge = f'<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200">{shop.status.title()}</span>'

            html_rows.append(f'''
            <tr class="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                  <div class="flex-shrink-0 h-10 w-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                    <svg class="h-6 w-6 text-blue-600 dark:text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                      <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 1 1 0 000 2H6a2 2 0 100 4h2a2 2 0 100 4h2a1 1 0 100 2 2 2 0 01-2 2H4a2 2 0 01-2-2V7a2 2 0 012-2z" clip-rule="evenodd"/>
                    </svg>
                  </div>
                  <div class="ml-4">
                    <div class="text-sm font-medium text-gray-900 dark:text-white">{shop.name}</div>
                    <div class="text-sm text-gray-500 dark:text-gray-400">{shop.email or "No email"}</div>
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">{shop.category or "Uncategorized"}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">{shop.owner_name or "-"}</td>
              <td class="px-6 py-4 whitespace-nowrap">{status_badge}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">{shop.bank_accounts.count()}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{shop.contact or "-"}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button onclick="openAddShopBankModal('{shop.shop_id}', '{shop.name}')" class="text-green-600 hover:text-green-900 dark:text-green-400 dark:hover:text-green-300 mr-3" title="Add Bank Account">
                  <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z"/>
                    <path fill-rule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clip-rule="evenodd"/>
                  </svg>
                </button>
                <button class="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 mr-3">View</button>
                <button class="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 mr-3">Edit</button>
                <button class="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300">Delete</button>
              </td>
            </tr>
            ''')

        return HttpResponse(''.join(html_rows), content_type='text/html')


class ShopCreateAPI(AgentSessionRequiredMixin, APIView):
    """API to create a new shop for the logged-in agent."""

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        data = None
        try:
            parsed = getattr(request, 'data', None)
            if isinstance(parsed, dict) and parsed:
                data = parsed
        except Exception:
            logger.exception('Unexpected error while accessing request.data for shop create payload')

        if data is None:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return Response({'success': False, 'message': 'Invalid JSON data.'}, status=400)
            except Exception:
                logger.exception('Unexpected error while parsing shop create payload')
                return Response({'success': False, 'message': 'Invalid request payload.'}, status=400)

        # Get agent from session
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'success': False, 'message': 'Agent not found.'}, status=404)

        # Validate required fields
        name = (data.get('name') or '').strip()
        if not name:
            return Response({'success': False, 'message': 'Shop name is required.'}, status=400)

        owner_name = (data.get('owner_name') or '').strip()
        email = (data.get('email') or '').strip()
        contact = (data.get('contact') or '').strip()
        category = (data.get('category') or '').strip()
        address = (data.get('address') or '').strip()
        status = (data.get('status') or 'active').strip() or 'active'

        if status not in dict(Shop.STATUS_CHOICES):
            return Response({'success': False, 'message': 'Invalid shop status.'}, status=400)

        if contact and len(contact) > 20:
            return Response({'success': False, 'message': 'Contact must be 20 characters or less.'}, status=400)

        if category and len(category) > 100:
            return Response({'success': False, 'message': 'Category must be 100 characters or less.'}, status=400)

        if owner_name and len(owner_name) > 255:
            return Response({'success': False, 'message': 'Owner name must be 255 characters or less.'}, status=400)

        # Create shop
        try:
            shop = Shop(
                name=name,
                owner_name=owner_name or None,
                category=category or None,
                contact=contact or None,
                email=email or None,
                address=address or None,
                status=status,
                agent=agent,
                branch=agent.branch,
            )

            # Ensure field validators run (e.g., EmailField)
            shop.full_clean()
            shop.save()

            if not ShopBankAccount.objects.filter(
                shop=shop,
                bank_name__isnull=True,
                account_number__isnull=True,
                ifsc_code__isnull=True,
            ).exists():
                ShopBankAccount.objects.create(
                    shop=shop,
                    account_holder_name=shop.name,
                    bank_name="cash/in hand",
                    account_number=None,
                    ifsc_code=None,
                    is_primary=True,
                    is_verified=True,
                )

            return Response({
                'success': True,
                'message': 'Shop created successfully.',
                'shop_id': shop.shop_id,
                'name': shop.name,
            }, status=201)
        except ValidationError as e:
            msg = 'Invalid shop data.'
            try:
                # e.message_dict is best when available
                if hasattr(e, 'message_dict'):
                    first_key = next(iter(e.message_dict.keys()), None)
                    if first_key and e.message_dict.get(first_key):
                        msg = str(e.message_dict[first_key][0])
                elif getattr(e, 'messages', None):
                    msg = str(e.messages[0])
            except Exception:
                pass
            return Response({'success': False, 'message': msg}, status=400)
        except (IntegrityError, DataError) as e:
            logger.exception('DB error creating shop')
            return Response({'success': False, 'message': 'Failed to create shop. Please check input values.'}, status=400)
        except Exception as e:
            logger.exception('Error creating shop')
            return Response({'success': False, 'message': 'Failed to create shop. Please try again.'}, status=500)


class ShopDetailUpdateAPI(AgentSessionRequiredMixin, APIView):
    """API to retrieve or update a specific shop for the logged-in agent."""

    def get(self, request, shop_id, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            shop = Shop.objects.get(shop_id=shop_id, agent__agent_id=agent_id)
            return Response({
                'success': True,
                'shop': {
                    'shop_id': shop.shop_id,
                    'name': shop.name,
                    'owner_name': shop.owner_name,
                    'category': shop.category,
                    'contact': shop.contact,
                    'email': shop.email,
                    'address': shop.address,
                    'status': shop.status,
                }
            }, status=200)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching shop {shop_id}: {str(e)}")
            return Response({'success': False, 'message': 'Failed to fetch shop details.'}, status=500)

    @method_decorator(csrf_exempt)
    def patch(self, request, shop_id, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({'success': False, 'message': 'Invalid JSON data.'}, status=400)

        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            shop = Shop.objects.get(shop_id=shop_id, agent__agent_id=agent_id)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)

        # Update fields if provided
        if 'name' in data:
            shop.name = data['name'].strip() or shop.name
        if 'owner_name' in data:
            shop.owner_name = data['owner_name'].strip() or None
        if 'category' in data:
            shop.category = data['category'].strip() or None
        if 'contact' in data:
            shop.contact = data['contact'].strip() or None
        if 'email' in data:
            shop.email = data['email'].strip() or None
        if 'address' in data:
            shop.address = data['address'].strip() or None
        if 'status' in data:
            shop.status = data['status']

        try:
            shop.save()
            return Response({
                'success': True,
                'message': 'Shop updated successfully.',
                'shop_id': shop.shop_id,
                'name': shop.name,
            }, status=200)
        except Exception as e:
            logger.error(f"Error updating shop {shop_id}: {str(e)}")
            return Response({'success': False, 'message': 'Failed to update shop. Please try again.'}, status=500)


class ShopDeleteAPI(AgentSessionRequiredMixin, APIView):
    """API to delete a shop and return its activity summary."""

    def get(self, request, shop_id, *args, **kwargs):
        """Get shop activity summary before deletion."""
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            shop = Shop.objects.get(shop_id=shop_id, agent__agent_id=agent_id)
            
            # Get related data counts
            bank_accounts_count = shop.bank_accounts.count()
            loan_applications_count = shop.loan_applications.count()
            
            # Get recent loan applications
            recent_loans = shop.loan_applications.order_by('-submitted_at')[:5]
            loan_details = []
            for loan in recent_loans:
                loan_details.append({
                    'loan_ref_no': loan.loan_ref_no,
                    'customer_name': loan.customer.full_name if loan.customer else 'N/A',
                    'amount': str(loan.loan_details.first().loan_amount) if loan.loan_details.exists() else 'N/A',
                    'status': loan.status,
                    'submitted_at': loan.submitted_at.strftime('%Y-%m-%d %H:%M') if loan.submitted_at else 'N/A'
                })
            
            # Get bank accounts
            bank_accounts = []
            for account in shop.bank_accounts.all():
                bank_accounts.append({
                    'bank_name': account.bank_name,
                    'account_number': account.account_number[-4:] if account.account_number else 'N/A',
                    'is_primary': account.is_primary
                })
            
            return Response({
                'success': True,
                'shop': {
                    'shop_id': shop.shop_id,
                    'name': shop.name,
                    'owner_name': shop.owner_name,
                    'status': shop.status,
                    'created_at': shop.created_at.strftime('%Y-%m-%d') if shop.created_at else 'N/A'
                },
                'activities': {
                    'bank_accounts_count': bank_accounts_count,
                    'loan_applications_count': loan_applications_count,
                    'bank_accounts': bank_accounts,
                    'recent_loans': loan_details
                }
            }, status=200)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching shop activities {shop_id}: {str(e)}")
            return Response({'success': False, 'message': 'Failed to fetch shop activities.'}, status=500)

    @method_decorator(csrf_exempt)
    def delete(self, request, shop_id, *args, **kwargs):
        """Soft delete the shop by setting status to inactive."""
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            shop = Shop.objects.get(shop_id=shop_id, agent__agent_id=agent_id)
            shop_name = shop.name
            
            # Soft delete: set status to inactive
            shop.status = 'inactive'
            shop.save()
            
            return Response({
                'success': True,
                'message': f'Shop "{shop_name}" has been marked as inactive.'
            }, status=200)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error soft deleting shop {shop_id}: {str(e)}")
            return Response({'success': False, 'message': 'Failed to delete shop. Please try again.'}, status=500)


class ShopBankAccountCreateAPI(AgentSessionRequiredMixin, APIView):
    """API to add a bank account to a shop."""

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        data = None
        try:
            parsed = getattr(request, 'data', None)
            if isinstance(parsed, dict) and parsed:
                data = parsed
        except Exception:
            logger.exception('Unexpected error while accessing request.data for shop bank account payload')

        if data is None:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                content_type = request.META.get('CONTENT_TYPE', '')
                raw_body = request.body
                try:
                    raw_preview = raw_body[:500].decode('utf-8', errors='replace')
                except Exception:
                    raw_preview = str(raw_body[:500])
                logger.error(
                    'Invalid JSON data for shop bank account. content_type=%s body_preview=%s',
                    content_type,
                    raw_preview,
                )
                return Response({'success': False, 'message': 'Invalid JSON data.'}, status=400)
            except Exception:
                logger.exception('Unexpected error while parsing shop bank account payload')
                return Response({'success': False, 'message': 'Invalid request payload.'}, status=400)

        def _get_str(payload, key):
            val = payload.get(key, '') if isinstance(payload, dict) else ''
            if val is None:
                return ''
            if isinstance(val, str):
                return val
            return str(val)

        # Get agent from session
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'success': False, 'message': 'Agent not found.'}, status=404)

        # Validate required fields
        shop_id = _get_str(data, 'shop_id').strip() or _get_str(data, 'shopId').strip()
        account_holder_name = _get_str(data, 'account_holder_name').strip()
        bank_name = _get_str(data, 'bank_name').strip()
        account_number = _get_str(data, 'account_number').strip()
        ifsc_code = _get_str(data, 'ifsc_code').strip().upper()

        if not shop_id:
            return Response({'success': False, 'message': 'Shop ID is required.'}, status=400)
        if not account_holder_name:
            return Response({'success': False, 'message': 'Account holder name is required.'}, status=400)
        if not bank_name:
            return Response({'success': False, 'message': 'Bank name is required.'}, status=400)
        if not account_number:
            return Response({'success': False, 'message': 'Account number is required.'}, status=400)
        if not ifsc_code:
            return Response({'success': False, 'message': 'IFSC code is required.'}, status=400)

        # Verify shop exists and belongs to this agent
        try:
            shop = Shop.objects.get(shop_id=shop_id, agent=agent)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found or access denied.'}, status=404)

        # Check if account number already exists for this shop
        if ShopBankAccount.objects.filter(shop=shop, account_number=account_number).exists():
            return Response({'success': False, 'message': 'This account number already exists for this shop.'}, status=400)

        # Create bank account
        try:
            is_primary = data.get('is_primary', False)
            if is_primary == 'true' or is_primary is True:
                is_primary = True
                # If setting as primary, unset any existing primary accounts for this shop
                ShopBankAccount.objects.filter(shop=shop, is_primary=True).update(is_primary=False)
            else:
                is_primary = False

            bank_account = ShopBankAccount.objects.create(
                shop=shop,
                account_holder_name=account_holder_name,
                bank_name=bank_name,
                account_number=account_number,
                ifsc_code=ifsc_code,
                upi_id=_get_str(data, 'upi_id').strip() or None,
                is_primary=is_primary,
            )
            return Response({
                'success': True,
                'message': 'Bank account added successfully.',
                'bank_account_id': bank_account.bank_account_id,
            }, status=201)
        except Exception as e:
            logger.exception('Error creating shop bank account')
            return Response({'success': False, 'message': 'Failed to add bank account. Please try again.'}, status=500)

    @method_decorator(csrf_exempt)
    def get(self, request, *args, **kwargs):
        """API to get bank accounts for a specific shop."""
        shop_id = request.GET.get('shop_id', '').strip()
        
        if not shop_id:
            return Response({'success': False, 'message': 'Shop ID is required.'}, status=400)

        # Get agent from session
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
            shop = Shop.objects.get(shop_id=shop_id, agent=agent)
            
            bank_accounts = ShopBankAccount.objects.filter(shop=shop).order_by('-created_at')
            
            # Convert to list of dictionaries
            bank_accounts_data = []
            for account in bank_accounts:
                bank_accounts_data.append({
                    'bank_account_id': account.bank_account_id,
                    'account_holder_name': account.account_holder_name,
                    'bank_name': account.bank_name,
                    'account_number': account.account_number,
                    'ifsc_code': account.ifsc_code,
                    'current_balance': account.current_balance,
                    'created_at': account.created_at.isoformat(),
                })
            
            return Response({
                'success': True,
                'bank_accounts': bank_accounts_data,
                'shop_name': shop.name,
            }, status=200)
            
        except Agent.DoesNotExist:
            return Response({'success': False, 'message': 'Agent not found.'}, status=404)
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)
        except Exception as e:
            logger.error(f"Error fetching bank accounts: {str(e)}")
            return Response({'success': False, 'message': 'Failed to fetch bank accounts. Please try again.'}, status=500)
