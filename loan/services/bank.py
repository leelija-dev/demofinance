import requests
import os
import uuid
import json
import random
from dotenv import load_dotenv

from typing import Optional

load_dotenv()

def _safe_json(response):
    try:
        return response.json()
    except json.JSONDecodeError as e:
        return {'status': 'error', 'message': f"API Error: {str(e)}. Raw Response: {response.text[:100]}"}

class CashfreeService:
    BASE_URL = os.getenv('CASHFREE_BASE_URL', 'https://sandbox.cashfree.com/verification')
    CLIENT_ID = os.getenv('CASHFREE_CLIENT_ID', '')
    CLIENT_SECRET = os.getenv('CASHFREE_CLIENT_SECRET', '')
    FORCE_MOCK = os.getenv('FORCE_CASHFREE_MOCK', 'false').lower() == 'true'

    @staticmethod
    def _get_headers():
        return {
            'x-client-id': CashfreeService.CLIENT_ID,
            'x-client-secret': CashfreeService.CLIENT_SECRET,
            'x-api-version': '2022-09-01',
            'Content-Type': 'application/json'
        }

    @staticmethod
    def verify_bank_account(account_number, ifsc, phone, name):
        if CashfreeService.FORCE_MOCK or not CashfreeService.CLIENT_ID or not CashfreeService.CLIENT_SECRET:
            return {
                'status': 'success',
                'data': {
                    'account_number': account_number,
                    'ifsc': ifsc,
                    'name_at_bank': name or 'Mock Account Name',
                    'bank_name': 'HDFC Bank Ltd',
                    'branch': 'Mumbai Main Branch',
                    'account_type': 'SAVINGS',
                    'city': 'Mumbai',
                    'state': 'Maharashtra',
                    'micr': '400240002',
                    'message': 'Bank Details fetched successfully.'
                }
            }

        url = f"{CashfreeService.BASE_URL}/bank-account/sync"
        payload = {
            "bank_account": account_number,
            "ifsc": ifsc,
            "name": name or "User",
            "phone": phone
        }
        
        headers = CashfreeService._get_headers()
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = _safe_json(response)
            if response.status_code == 200:
                if 'status' in data and data['status'] == 'error': 
                    print(data)
                    return data
                print({'status': 'success', 'data': data})
                return {'status': 'success', 'data': data}
            
            error_msg = 'Bank verification failed.'
            if isinstance(data, dict):
                error_msg = data.get('message', data.get('type', error_msg))
            return {'status': 'error', 'message': error_msg}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}







class AutoPaymentService:
    # Use Production URL if explicitly provided, else fallback to Sandbox
    _base_config = os.getenv('CASHFREE_BASE_URL_PROD') or os.getenv('CASHFREE_BASE_URL', 'https://sandbox.cashfree.com/verification')
    BASE_URL = _base_config.replace('/verification', '/pg')
    CLIENT_ID = os.getenv('CASHFREE_PG_CLIENT_ID') or os.getenv('CASHFREE_CLIENT_ID', '')
    CLIENT_SECRET = os.getenv('CASHFREE_PG_CLIENT_SECRET') or os.getenv('CASHFREE_CLIENT_SECRET', '')
    FORCE_MOCK = os.getenv('FORCE_CASHFREE_MOCK', 'false').lower() == 'true'

    @staticmethod
    def _get_headers():
        return {
            'x-client-id': AutoPaymentService.CLIENT_ID,
            'x-client-secret': AutoPaymentService.CLIENT_SECRET,
            'x-api-version': '2023-08-01',
            'Content-Type': 'application/json',
            'User-Agent': 'Django-KYC-App/1.0'
        }

    @staticmethod
    def create_subscription(customer_name, customer_email, customer_phone, plan_name, amount, return_url):
        """Create a subscription and return the checkout link for eNACH authorization."""
        if AutoPaymentService.FORCE_MOCK or not AutoPaymentService.CLIENT_ID or not AutoPaymentService.CLIENT_SECRET:
            mock_sub_id = f"sub_{uuid.uuid4().hex[:12]}"
            mock_checkout_url = f"{return_url}?subscription_id={mock_sub_id}&status=SUCCESS"
            return {
                'status': 'success',
                'subscription_id': mock_sub_id,
                'checkout_url': mock_checkout_url,
                'message': 'Mock subscription created.'
            }

        url = f"{AutoPaymentService.BASE_URL}/subscriptions"
        
        subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
        
        payload = {
            "subscription_id": subscription_id,
            "customer_details": {
                "customer_name": customer_name or "Test User",
                "customer_email": customer_email or "test@example.com",
                "customer_phone": customer_phone or "9999999999"
            },
            "plan_details": {
                "plan_name": __import__('re').sub(r'[^a-zA-Z0-9]', '', plan_name or f"Monthly {amount}")[:100],
                "plan_type": "PERIODIC",
                "plan_currency": "INR",
                "plan_amount": float(amount),
                "plan_max_amount": float(amount) * 2,
                "plan_intervals": 1,
                "plan_interval_type": "MONTH"
            },
            "subscription_meta": {
                "return_url": return_url + "?subscription_id={subscription_id}"
            },
            "subscription_expiry_time": "2026-05-31T23:59:59Z", # Arbitrary future expiry
            "auto_renew": True
        }

        try:
            headers = AutoPaymentService._get_headers()
            
            # --- START DEBUG LOGGING ---
            print("\n" + "="*50)
            print("CASHFREE SUBSCRIPTIONS API REQUEST")
            print("="*50)
            print(f"URL: {url}")
            print(f"Headers: {json.dumps(headers, indent=2)}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print("-" * 50)
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = _safe_json(response)
            
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Body: {json.dumps(data, indent=2)}")
            print("="*50 + "\n")
            # --- END DEBUG LOGGING ---
            
            if response.status_code == 200:
                session_id = data.get('subscription_session_id')
                sub_id = data.get('subscription_id') or subscription_id
                
                if session_id:
                    return {
                        'status': 'success', 
                        'subscription_id': sub_id,
                        'subscription_session_id': session_id,
                        'raw_data': data
                    }
                else:
                    return {'status': 'error', 'message': 'API did not return a subscription session ID.', 'raw_data': data}

            error_msg = 'Subscription creation failed.'
            if isinstance(data, dict):
                error_msg = data.get('message', data.get('type', error_msg))
            return {'status': 'error', 'message': error_msg, 'raw_data': data}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}
