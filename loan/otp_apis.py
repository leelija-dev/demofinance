import requests
import json
import time
import base64
import re
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging
from loan.models import CustomerDetail, LoanCloseRequest, DocumentReupload
from loan.services.identity import IdentitySandboxService

logger = logging.getLogger(__name__)

class SendMobileOTPAPI(APIView):
    """
    API to send OTP to mobile number using api.sandbox.co.in
    """
    
    def post(self, request):
        mobile = request.data.get('mobile')
        
        if not mobile:
            return Response({
                'success': False,
                'message': 'Mobile number is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(mobile) != 10 or not mobile.isdigit():
            return Response({
                'success': False,
                'message': 'Invalid mobile number format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Using api.sandbox.co.in for OTP sending
            url = "https://api.sandbox.co.in/otp/send"
            
            payload = {
                "mobile": mobile,
                "sender_id": "SNDLR",
                "message": f"Your OTP for loan application verification is {{otp}}. Do not share this with anyone. - LoanApp",
                "template_id": "1207161696534847499"
            }
            
            headers = {
                "Authorization": f"Bearer {getattr(settings, 'IDENTITY_API_KEY', '')}",
                "X-Api-Secret": getattr(settings, 'IDENTITY_API_SECRET', ''),
                "Content-Type": "application/json"
            }
            
            # Production API call
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    # Store OTP reference in session
                    request.session[f'mobile_otp_ref_{mobile}'] = data.get('request_id')
                    
                    return Response({
                        'success': True,
                        'message': 'OTP sent successfully'
                    })
                else:
                    return Response({
                        'success': False,
                        'message': data.get('message', 'Failed to send OTP')
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.error(f"Mobile OTP API error: {response.status_code} - {response.text}")
                return Response({
                    'success': False,
                    'message': 'Failed to send OTP. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Mobile OTP API exception: {str(e)}")
            return Response({
                'success': False,
                'message': 'Network error. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Mobile OTP unexpected error: {str(e)}")
            return Response({
                'success': False,
                'message': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyMobileOTPAPI(APIView):
    """
    API to verify mobile OTP
    """
    
    def post(self, request):
        mobile = request.data.get('mobile')
        otp = request.data.get('otp')
        
        if not mobile or not otp:
            return Response({
                'success': False,
                'message': 'Mobile number and OTP are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Use api.sandbox.co.in verification
            otp_ref = request.session.get(f'mobile_otp_ref_{mobile}')
            
            if not otp_ref:
                return Response({
                    'success': False,
                    'message': 'OTP not sent or expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            url = "https://api.sandbox.co.in/otp/verify"
            
            payload = {
                "request_id": otp_ref,
                "otp": otp,
                "mobile": mobile
            }
            
            headers = {
                "Authorization": f"Bearer {getattr(settings, 'IDENTITY_API_KEY', '')}",
                "X-Api-Secret": getattr(settings, 'IDENTITY_API_SECRET', ''),
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success' and data.get('verified'):
                    # Clear OTP reference
                    del request.session[f'mobile_otp_ref_{mobile}']
                    
                    # Mark mobile as verified
                    request.session[f'mobile_verified_{mobile}'] = True
                    
                    return Response({
                        'success': True,
                        'message': 'Mobile number verified successfully'
                    })
                else:
                    return Response({
                        'success': False,
                        'message': data.get('message', 'Invalid OTP')
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.error(f"Mobile OTP verification error: {response.status_code} - {response.text}")
                return Response({
                    'success': False,
                    'message': 'Failed to verify OTP. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Mobile OTP verification error: {str(e)}")
            return Response({
                'success': False,
                'message': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendAadhaarOTPAPI(APIView):
    """
    API to send OTP to Aadhaar number using IdentitySandboxService
    """
    
    def post(self, request):
        aadhaar = request.data.get('aadhaar')
        continueWithExistingCustomer = request.data.get('continue_with_existing_customer')
        
        if not aadhaar:
            return Response({
                'success': False,
                'message': 'Aadhaar number is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(aadhaar) != 12 or not aadhaar.isdigit():
            return Response({
                'success': False,
                'message': 'Invalid Aadhaar number format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check if Aadhaar number already exists in database
            existing_customer = CustomerDetail.objects.filter(adhar_number=aadhaar).first()
            
            if existing_customer and not continueWithExistingCustomer:
                # Check if customer should be allowed to proceed (only if they have rejected loans or approved close requests)
                rejected_statuses = ['reject', 'rejected_by_branch', 'hq_rejected']
                has_rejected_loans = existing_customer.loan_applications.filter(status__in=rejected_statuses).exists()

                # Check for approved loan close requests
                has_approved_close_requests = LoanCloseRequest.objects.filter(
                    loan_application__customer=existing_customer,
                    status='approved'
                ).exists()
                
                # Only allow proceeding if customer has rejected loans OR approved close requests
                can_proceed = has_rejected_loans or has_approved_close_requests
                
                # Fetch customer basic details and loan history
                from django.forms.models import model_to_dict
                customer_data = model_to_dict(existing_customer)
                customer_data['date_of_birth'] = existing_customer.date_of_birth.strftime('%d-%m-%Y') if existing_customer.date_of_birth else None
                customer_data['customer_id'] = existing_customer.customer_id
                customer_data['aadhar_number'] = existing_customer.adhar_number
                
                # Fetch customer address data
                try:
                    address_data = None
                    if hasattr(existing_customer, 'address') and existing_customer.address:
                        address = existing_customer.address
                        address_data = model_to_dict(address)
                except:
                    address_data = None
                
                # Fetch customer documents data
                try:
                    # Helper to get latest document reupload or original
                    import os

                    def get_latest_document(loan_application, doc_type, original_file):
                        # Special handling for residential proof: check both possible doc_type values
                        reupload = DocumentReupload.objects.filter(
                            loan_application=loan_application,
                            document_type=doc_type
                        ).order_by('-uploaded_at').first()
                        print("reupload ->", reupload)
                        if reupload and reupload.uploaded_file and os.path.exists(str(reupload.uploaded_file)):
                            try:
                                with open(str(reupload.uploaded_file), 'rb') as f:
                                    return base64.b64encode(f.read()).decode('utf-8')
                            except Exception:
                                print("reupload exception ->", reupload)
                                pass
                        # Fall back to original file
                        if original_file and hasattr(original_file, 'path') and os.path.exists(str(original_file.path)):
                            try:
                                with open(str(original_file.path), 'rb') as f:
                                    return base64.b64encode(f.read()).decode('utf-8')
                            except Exception as e:
                                print("original file exception ->", original_file, e)
                                raise e
                        print("reupload none ->", reupload)
                        return None

                    documents_data = {}
                    # Find the latest loan application for this customer to get documents
                    latest_loan = existing_customer.loan_applications.order_by('-submitted_at').first()
                    print(f"latest_loan - ${latest_loan}")
                    print(f"latest_loan.documents.id_proof - ${latest_loan.documents.id_proof}")
                    if latest_loan and hasattr(latest_loan, 'documents') and latest_loan.documents:
                        print('kkkkkkkkkk')
                        documents_data = {
                            'guarantor_id_proof': get_latest_document(latest_loan, 'guarantor_id_proof', latest_loan.documents.guarantor_id_proof),
                            'id_proof': get_latest_document(latest_loan, 'id_proof', latest_loan.documents.id_proof),
                            'id_proof_back': get_latest_document(latest_loan, 'id_proof_back', latest_loan.documents.id_proof_back),
                            'photo': get_latest_document(latest_loan, 'photo', latest_loan.documents.photo),
                            'pan_card_document': get_latest_document(latest_loan, 'pan_card_document', getattr(latest_loan.documents, 'pan_card_document', None)),
                            'income_proof': get_latest_document(latest_loan, 'income_proof', latest_loan.documents.income_proof),
                            'signature': get_latest_document(latest_loan, 'signature', latest_loan.documents.signature),
                            'collateral': get_latest_document(latest_loan, 'collateral', latest_loan.documents.collateral),
                            'residential_proof_file': get_latest_document(latest_loan, 'residential_proof_file', latest_loan.documents.residential_proof_file),
                        }
                        print('jjjjjjjjjjjj')
                except Exception as e:
                    logger.error(f"Error fetching customer documents: {str(e)}")
                    documents_data = None
                
                # Add documents data to customer_data
                print(f'documents_data -> ${documents_data}')
                if documents_data:
                    customer_data['documents_data'] = documents_data
                
                # Fetch customer bank account data
                try:
                    bank_data = None
                    if hasattr(existing_customer, 'account') and existing_customer.account:
                        account = existing_customer.account
                        bank_data = model_to_dict(account)
                        bank_data['account_type'] = account.get_account_type_display() if account.account_type else None
                        # bank_data = {
                        #     'account_number': account.account_number,
                        #     'bank_name': account.bank_name,
                        #     'ifsc_code': account.ifsc_code,
                        #     'account_type': account.get_account_type_display() if account.account_type else None,
                        # }
                except:
                    bank_data = None
                
                # Add address and bank data to customer_data
                if address_data:
                    customer_data['address_data'] = address_data
                if bank_data:
                    customer_data['bank_data'] = bank_data
                
                # Fetch loan history
                loans = existing_customer.loan_applications.all()
                loan_history = []
                for loan in loans:
                    loan_history.append({
                        'loan_ref_no': loan.loan_ref_no,
                        'status': loan.get_status_display(),
                        'submitted_at': loan.submitted_at.strftime('%d-%m-%Y %H:%M') if loan.submitted_at else None,
                        'approved_at': loan.approved_at.strftime('%d-%m-%Y %H:%M') if loan.approved_at else None,
                        'disbursed_at': loan.disbursed_at.strftime('%d-%m-%Y %H:%M') if loan.disbursed_at else None,
                    })
                
                return Response({
                    'success': True,
                    'customer_exists': True,
                    'customer_blocked': can_proceed, # not can_proceed,
                    'message': 'Customer found in database and eligible to proceed' if can_proceed else 'Customer found in database but not eligible to proceed',
                    'customer_data': customer_data,
                    'loan_history': loan_history
                })
            
            # Aadhaar not found, proceed with OTP sending
            # Use IdentitySandboxService for Aadhaar OTP
            result = IdentitySandboxService.aadhaar_generate_otp(aadhaar)
            
            if result.get('status') == 'success':
                # Store OTP reference in session
                ref_id = result.get('ref_id')
                request.session[f'aadhaar_otp_ref_{aadhaar}'] = ref_id
                
                return Response({
                    'success': True,
                    'customer_exists': False,
                    'message': result.get('message', 'OTP sent successfully'),
                    'ref_id': ref_id
                })
            else:
                return Response({
                    'success': False,
                    'customer_exists': False,
                    'message': result.get('message', 'Failed to send OTP')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Aadhaar OTP API error: {str(e)}")
            return Response({
                'success': False,
                'message': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyAadhaarOTPAPI(APIView):
    """
    API to verify Aadhaar OTP and fetch user details using IdentitySandboxService
    """
    
    def post(self, request):
        aadhaar = request.data.get('aadhaar')
        otp = request.data.get('otp')
        
        if not aadhaar or not otp:
            return Response({
                'success': False,
                'message': 'Aadhaar number and OTP are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Use IdentitySandboxService for verification
            otp_ref = request.session.get(f'aadhaar_otp_ref_{aadhaar}')
            
            if not otp_ref:
                return Response({
                    'success': False,
                    'message': 'OTP not sent or expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = IdentitySandboxService.aadhaar_submit_otp(otp, otp_ref)
            
            if result.get('status') == 'success':
                # Clear OTP reference
                del request.session[f'aadhaar_otp_ref_{aadhaar}']
                
                # Mark Aadhaar as verified
                request.session[f'aadhaar_verified_{aadhaar}'] = True
                
                # Extract Aadhaar data from service response
                aadhaar_data = result.get('data', {})
                
                return Response({
                    'success': True,
                    'message': 'Aadhaar verified successfully',
                    'aadhaar_data': aadhaar_data
                })
            else:
                return Response({
                    'success': False,
                    'message': result.get('message', 'Invalid OTP')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Aadhaar OTP verification error: {str(e)}")
            return Response({
                'success': False,
                'message': 'An unexpected error occurred. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@method_decorator(csrf_exempt, name='dispatch')
class PANVerificationAPI(APIView):
    """API to verify PAN-Aadhaar linking"""
    
    def post(self, request, *args, **kwargs):
        try:
            # Parse request data using DRF's built-in parser
            data = request.data
            pan_number = (data.get('pan_number') or '').strip()
            aadhaar_number_raw = (data.get('aadhaar_number') or '').strip()
            aadhaar_number = re.sub(r'\D', '', aadhaar_number_raw)
            
            if not pan_number or not aadhaar_number:
                return Response({
                    'success': False,
                    'message': 'PAN number and Aadhaar number are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate PAN format
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan_number.upper()):
                return Response({
                    'success': False,
                    'message': 'Invalid PAN format. Format: 5 letters, 4 digits, 1 letter'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate Aadhaar format (12 digits)
            if not re.match(r'^\d{12}$', aadhaar_number):
                return Response({
                    'success': False,
                    'message': 'Invalid Aadhaar format. Must be 12 digits'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Call the PAN-Aadhaar linking service
            result = IdentitySandboxService.pan_aadhaar_link_check(pan_number.upper(), aadhaar_number)
            
            # Validate service response
            if not isinstance(result, dict):
                return Response({
                    'success': False,
                    'message': 'Invalid response from verification service'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            if result.get('status') == 'success':
                aadhaar_seeding_status = result.get('data', {}).get('aadhaar_seeding_status', 'n')
                is_linked = aadhaar_seeding_status.lower() in ['y', 'yes']
                
                return Response({
                    'success': True,
                    'is_linked': is_linked,
                    'message': 'PAN is linked to Aadhaar' if is_linked else 'PAN is not linked to Aadhaar',
                    'data': result.get('data', {})
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': result.get('message', 'Failed to verify PAN-Aadhaar linking')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"PAN-Aadhaar verification error: {str(e)}")
            return Response({
                'success': False,
                'message': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)