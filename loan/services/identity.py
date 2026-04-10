import requests
import os
import uuid
import json
from dotenv import load_dotenv

from typing import Optional

load_dotenv()

def _safe_json(response):
    try:
        return response.json()
    except json.JSONDecodeError as e:
        return {'status': 'error', 'message': f"API Error: {str(e)}. Raw Response: {response.text[:100]}"}

class IdentitySandboxService:
    BASE_URL = os.getenv('IDENTITY_API_BASE_URL', 'https://api.sandbox.co.in').rstrip('/')
    API_KEY = os.getenv('IDENTITY_API_KEY', '')
    API_SECRET = os.getenv('IDENTITY_API_SECRET', '')
    _access_token: Optional[str] = None
    _token_generated_at: float = 0

    @staticmethod
    def _get_access_token():
        import time
        current_time = time.time()
        
        # 24 hours = 86400 seconds. Re-auth after 23.9 hours to be safe.
        expiry_seconds = 86400 - 300 # 5 minute buffer
        
        if IdentitySandboxService._access_token and (current_time - IdentitySandboxService._token_generated_at) < expiry_seconds:
            return IdentitySandboxService._access_token
        
        print(f"[Sandbox] Token expired or missing. Authenticating... (Last: {IdentitySandboxService._token_generated_at})")
        
        url = f"{IdentitySandboxService.BASE_URL}/authenticate"
        headers = {
            'x-api-key': IdentitySandboxService.API_KEY,
            'x-api-secret': IdentitySandboxService.API_SECRET,
            'x-api-version': '1.0'
        }
        try:
            response = requests.post(url, headers=headers, timeout=10)
            data = _safe_json(response)
            if response.status_code == 200 and isinstance(data, dict):
                token = data.get('access_token') or data.get('token')
                if not token and 'data' in data and isinstance(data['data'], dict):
                    token = data['data'].get('token') or data['data'].get('access_token')
                
                if token:
                    IdentitySandboxService._access_token = str(token)
                    IdentitySandboxService._token_generated_at = time.time()
                    return str(token)
            
            print(f"[Sandbox Auth] Failed to get token. Status: {response.status_code}, Response: {data}")
        except Exception as e:
            print(f"[Sandbox Auth] Exception: {str(e)}")
        return None

    @staticmethod
    def _get_auth_headers():
        token = IdentitySandboxService._get_access_token()
        headers = {
            'x-api-key': IdentitySandboxService.API_KEY,
            'x-api-version': '1.0',
            'Content-Type': 'application/json'
        }
        if token:
            # headers['Authorization'] = str(token) if str(token).startswith('Bearer ') else f'Bearer {token}'
            headers['Authorization'] = str(token)
        else:
            headers['x-api-secret'] = IdentitySandboxService.API_SECRET
        return headers

    @staticmethod
    def aadhaar_generate_otp(aadhaar_number):
        if not IdentitySandboxService.API_KEY or os.getenv('FORCE_CASHFREE_MOCK', 'false').lower() == 'true':
            return {'status': 'success', 'ref_id': str(uuid.uuid4()), 'message': 'Mock OTP sent (Sandbox.co.in).'}

        url = f"{IdentitySandboxService.BASE_URL}/kyc/aadhaar/okyc/otp"
        payload = {
            "@entity": "in.co.sandbox.kyc.aadhaar.okyc.otp.request",
            "aadhaar_number": aadhaar_number,
            "consent": "Y",
            "reason": "Verify identity for onboarding"
        }

        def _attempt():
            try:
                headers = IdentitySandboxService._get_auth_headers()
                
                # Debug Prints for Request
                print(f"\n--- [Sandbox Request Details] ---")
                print(f"URL: {url}")
                print(f"Headers: {json.dumps(headers, indent=2)}")
                print(f"Body: {json.dumps(payload, indent=2)}")
                print(f"---------------------------------\n")

                response = requests.post(url, json=payload, headers=headers, timeout=15)
                data = _safe_json(response)
                print(f"[Sandbox OTP] Status: {response.status_code}, Response: {data}")
                
                if response.status_code != 200:
                    print(f"Raw Error Response: {response.text}")

                return response, data
            except Exception as e:
                print(f"[Sandbox Request Exception]: {str(e)}")
                return None, str(e)

        response, data = _attempt()
        
        # Retry once if Forbidden/Unauthorized (token might be stale)
        if response and response.status_code in [401, 403]:
            print("[Sandbox] Forbidden/Unauthorized. Retrying with fresh token...")
            IdentitySandboxService._access_token = None
            response, data = _attempt()

        if response and response.status_code == 200 and isinstance(data, dict) and 'data' in data:
            return {'status': 'success', 'ref_id': data['data'].get('reference_id'), 'message': 'OTP sent successfully.'}
        
        error_msg = data.get('message', f'Status: {getattr(response, "status_code", "Error")}') if isinstance(data, dict) else str(data)
        return {'status': 'error', 'message': f'Failed to send OTP via Sandbox.co.in ({error_msg})'}

    @staticmethod
    def aadhaar_submit_otp(otp, ref_id):
        if not IdentitySandboxService.API_KEY or os.getenv('FORCE_CASHFREE_MOCK', 'false').lower() == 'true':
            return {
                'status': 'success',
                'data': {
                    'name': 'John Doe (Sandbox Mock)',
                    'dob': '01-01-1990',
                    'gender': 'M',
                    'address': '123, Sandbox Street',
                    'aadhaar_number': 'XXXXXXXX1234'
                }
            }

        url = f"{IdentitySandboxService.BASE_URL}/kyc/aadhaar/okyc/otp/verify"
        payload = {
            "@entity": "in.co.sandbox.kyc.aadhaar.okyc.request",
            "otp": str(otp),
            "reference_id": str(ref_id)
        }
        try:
            headers=IdentitySandboxService._get_auth_headers()
            # Debug Prints for Request
            print(f"\n--- [Sandbox Request Details] ---")
            print(f"URL: {url}")
            print(f"Headers: {json.dumps(headers, indent=2)}")
            print(f"Body: {json.dumps(payload, indent=2)}")
            print(f"---------------------------------\n")
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = _safe_json(response)
            print(f"[Sandbox OTP Verification] Status: {response.status_code}, Response: {data}")
            if response.status_code == 200 and isinstance(data, dict) and 'data' in data:
                return {'status': 'success', 'data': data['data']}
            
            error_msg = "Unknown error"
            if isinstance(data, dict):
                error_msg = data.get('message', f'Status: {response.status_code}')
            return {'status': 'error', 'message': f'OTP verification failed via Sandbox.co.in ({error_msg})'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @staticmethod
    def pan_aadhaar_link_check(pan, aadhaar):
        if not IdentitySandboxService.API_KEY or os.getenv('FORCE_CASHFREE_MOCK', 'false').lower() == 'true':
            return {'status': 'success', 'data': {'aadhaar_seeding_status': 'y'}, 'message': 'Mock Linking Check Success.'}

        url = f"{IdentitySandboxService.BASE_URL}/kyc/pan-aadhaar/status"
        payload = {
            "@entity": "in.co.sandbox.kyc.pan_aadhaar.status",
            "pan": str(pan),
            "aadhaar_number": str(aadhaar),
            "consent": "Y",
            "reason": "Verify PAN-Aadhaar linking for onboarding"
        }
        try:
            response = requests.post(url, json=payload, headers=IdentitySandboxService._get_auth_headers(), timeout=15)
            data = _safe_json(response)
            print(f"[Sandbox PAN-Aadhaar Linking Check] Status: {response.status_code}, Response: {data}")
            if response.status_code == 200 and isinstance(data, dict) and 'data' in data:
                return {'status': 'success', 'data': data['data']}
            
            error_msg = data.get('message', f'Status: {response.status_code}') if isinstance(data, dict) else "Unknown error"
            return {'status': 'error', 'message': f'Linking check failed via Sandbox.co.in ({error_msg})'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
