"""Surepass credit score service (CIBIL / Equifax) + business rule helpers.

The credit check is manual: it runs from the new-application form (Equifax
pre-check) before the application is submitted, and the result is linked to
the loan on submit. Follows the same pattern as loan/services/identity.py
(env-driven config, mock mode when no token).

Console          : https://console.surepass.app/
Docs             : https://app.surepass.app/docs/kyc
Equifax (API)    : https://kyc-api.surepass.app/api/v1/credit-report-v2/fetch-report
Docs sample host : https://app.surepass.app/production/... (may require a different token)
Sandbox URL      : https://sandbox.surepass.app
"""

import os
import re
import json
import logging
import base64
from pathlib import Path

import requests
from dotenv import load_dotenv

# Always load project .env (override so shell/env leftovers don't keep a stale token)
_ENV_FILE = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(_ENV_FILE, override=True)

logger = logging.getLogger(__name__)


def _safe_json(response):
    try:
        return response.json()
    except json.JSONDecodeError:
        raw = (response.text or '').strip()
        status_code = getattr(response, 'status_code', None)
        if status_code == 404 or raw.lower().startswith('<!doctype html') or '<title>404' in raw.lower():
            return {
                'status': 'error',
                'message': (
                    f'Equifax endpoint not found on Surepass (HTTP {status_code}). '
                    'This usually means the Equifax credit-report product is not enabled '
                    'for your Surepass account. Ask Surepass support to enable '
                    '"Equifax Credit Report" and confirm the exact API path in '
                    'https://console.surepass.app/ / https://app.surepass.app/docs/kyc'
                ),
                'status_code': status_code,
            }
        if status_code == 401 and 'whitelist' in raw.lower():
            return {
                'status': 'error',
                'message': (
                    'Surepass rejected the request: IP not whitelisted. '
                    'Add this server\'s public IP in the Surepass console whitelist.'
                ),
                'status_code': status_code,
            }
        snippet = raw[:180].replace('\n', ' ')
        return {
            'status': 'error',
            'message': f'Surepass returned a non-JSON response (HTTP {status_code}): {snippet}',
            'status_code': status_code,
        }


# ---------------------------------------------------------------------------
# CIBIL business rule (policy) configuration
# ---------------------------------------------------------------------------

def get_cibil_policy():
    """Score bands for the CIBIL business rule (env-configurable).

    decision = 'pass'          -> score >= CIBIL_MIN_SCORE
    decision = 'manual_review' -> CIBIL_REVIEW_SCORE <= score < CIBIL_MIN_SCORE,
                                  or no credit history / score unavailable
    decision = 'fail'          -> score < CIBIL_REVIEW_SCORE
    """
    try:
        min_score = int(os.getenv('CIBIL_MIN_SCORE', '650'))
    except (TypeError, ValueError):
        min_score = 650
    try:
        review_score = int(os.getenv('CIBIL_REVIEW_SCORE', '600'))
    except (TypeError, ValueError):
        review_score = 600
    enforce = os.getenv('CIBIL_ENFORCE_MIN_SCORE', 'false').strip().lower() in ('true', '1', 'yes')
    return {'min_score': min_score, 'review_score': review_score, 'enforce': enforce}


def classify_score(score):
    """Map a CIBIL score to a business-rule decision: pass / manual_review / fail."""
    policy = get_cibil_policy()
    if score is None or score <= 0:
        # New-to-credit customers (no history) always go to manual review.
        return 'manual_review'
    if score >= policy['min_score']:
        return 'pass'
    if score >= policy['review_score']:
        return 'manual_review'
    return 'fail'


def evaluate_cibil_gate(loan_application):
    """Business rule applied at branch/HQ approval time.

    Returns (allowed: bool, message: Optional[str]). Never raises, and never
    blocks unless CIBIL_ENFORCE_MIN_SCORE=True AND a successful check exists
    with a 'fail' decision — so existing approval flows are unaffected by
    default.
    """
    try:
        policy = get_cibil_policy()
        if not policy['enforce']:
            return True, None
        latest = loan_application.credit_checks.order_by('-fetched_at').first()
        if latest is None or latest.status != 'success':
            return True, None
        if latest.decision == 'fail':
            return False, (
                f"CIBIL score {latest.score} is below the minimum required "
                f"({policy['review_score']}). Application cannot be approved as per credit policy."
            )
        return True, None
    except Exception as e:
        logger.warning("evaluate_cibil_gate failed (allowing approval): %s", e)
        return True, None


# ---------------------------------------------------------------------------
# Surepass API client
# ---------------------------------------------------------------------------

class SurepassCreditService:
    # Equifax credit-report-v2 lives under app.surepass.app/production
    # Config is read at call-time via helpers so .env changes apply after restart.
    CIBIL_ENDPOINT_DEFAULT = '/api/v1/credit-report-cibil/fetch-report'
    EQUIFAX_ENDPOINT_DEFAULT = '/api/v1/credit-report-v2/fetch-report'
    EQUIFAX_PDF_ENDPOINT_DEFAULT = '/api/v1/credit-report-v2/fetch-pdf-report'
    BASE_URL_DEFAULT = 'https://kyc-api.surepass.app'

    @staticmethod
    def _get_base_url():
        return (os.getenv('SUREPASS_API_BASE_URL') or SurepassCreditService.BASE_URL_DEFAULT).rstrip('/')

    @staticmethod
    def _get_api_token():
        """Read and normalize the Surepass bearer token from env."""
        token = (os.getenv('SUREPASS_API_TOKEN') or '').strip().strip('"').strip("'")
        if token.lower().startswith('bearer '):
            token = token[7:].strip()
        return token

    @staticmethod
    def _get_endpoint(bureau):
        if bureau == 'equifax':
            return os.getenv('SUREPASS_EQUIFAX_ENDPOINT') or SurepassCreditService.EQUIFAX_ENDPOINT_DEFAULT
        return os.getenv('SUREPASS_CIBIL_ENDPOINT') or SurepassCreditService.CIBIL_ENDPOINT_DEFAULT

    @staticmethod
    def _get_timeout():
        try:
            return int(os.getenv('SUREPASS_TIMEOUT_SECONDS', '30'))
        except (TypeError, ValueError):
            return 30

    @staticmethod
    def _token_identity_hint(token):
        """Decode JWT payload (no verify) to surface sandbox vs production identity."""
        try:
            parts = str(token or '').split('.')
            if len(parts) < 2:
                return None
            pad = '=' * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode('utf-8'))
            return payload.get('identity') or payload.get('email')
        except Exception:
            return None

    # Back-compat aliases used by older references / debugging
    @classmethod
    def _sync_cached_config(cls):
        cls.BASE_URL = cls._get_base_url()
        cls.API_TOKEN = cls._get_api_token()
        cls.CIBIL_ENDPOINT = cls._get_endpoint('cibil')
        cls.EQUIFAX_ENDPOINT = cls._get_endpoint('equifax')
        cls.EQUIFAX_PDF_ENDPOINT = (
            os.getenv('SUREPASS_EQUIFAX_PDF_ENDPOINT')
            or cls.EQUIFAX_PDF_ENDPOINT_DEFAULT
        )
        cls.TIMEOUT_SECONDS = cls._get_timeout()

    @staticmethod
    def _is_mock():
        token = SurepassCreditService._get_api_token()
        return (
            not token
            or os.getenv('FORCE_SUREPASS_MOCK', 'false').strip().lower() == 'true'
        )

    @staticmethod
    def _mock_score(pan):
        # Deterministic per-PAN so repeated checks return the same score while testing.
        seed = sum(ord(c) for c in str(pan or 'MOCK'))
        return 550 + (seed % 301)  # 550 - 850

    @staticmethod
    def _normalize_mobile(contact):
        digits = re.sub(r'\D', '', str(contact or ''))
        return digits[-10:] if len(digits) >= 10 else None

    @staticmethod
    def _normalize_gender(gender):
        g = str(gender or '').strip().lower()
        if g.startswith('m'):
            return 'male'
        if g.startswith('f'):
            return 'female'
        return None

    @staticmethod
    def _mock_full_report(name, pan, mobile, gender, score, bureau):
        """Full mock report in the Equifax IDCR (CCRResponse) shape returned by
        Surepass — deterministic per PAN so the modal shows realistic content
        while testing."""
        from datetime import date
        seed = sum(ord(c) for c in str(pan or 'MOCK'))
        today = date.today()
        opened_year = today.year - 2 - (seed % 4)
        balance = 50000 + (seed % 9) * 25000
        sanction = balance + 60000 + (seed % 5) * 10000
        emi = 1500 + (seed % 7) * 500
        is_bad = score < 600
        pay_status = '090' if is_bad else '000'

        def history(months, status):
            out = []
            y, m = today.year, today.month
            for _ in range(months):
                out.append({
                    'key': f"{m:02d}-{y % 100:02d}",
                    'PaymentStatus': status,
                    'SuitFiledStatus': '*',
                    'AssetClassificationStatus': 'STD' if status in ('000', 'STD') else 'SUB',
                })
                m -= 1
                if m == 0:
                    y, m = y - 1, 12
            return out

        accounts = [
            {
                'seq': '1',
                'AccountNumber': f"XXXXXXXX{seed % 10000:04d}",
                'Institution': 'HDFC Bank Limited',
                'AccountType': 'Personal Loan',
                'OwnershipType': 'Individual',
                'Open': 'Yes',
                'AccountStatus': 'Current Account',
                'Balance': str(balance),
                'PastDueAmount': str((seed % 4) * 2500) if is_bad else '0',
                'LastPayment': str(emi),
                'LastPaymentDate': today.strftime('%Y-%m-%d'),
                'SanctionAmount': str(sanction),
                'CreditLimit': '',
                'InterestRate': '9.15',
                'RepaymentTenure': '36',
                'TermFrequency': 'Monthly',
                'MonthlyPaymentAmount': str(emi),
                'WriteOffAmount': '',
                'AssetClassification': 'Standard',
                'DisputeCode': '',
                'SuitFiledStatus': '',
                'DateOpened': f"{opened_year}-06-15",
                'DateReported': today.strftime('%Y-%m-%d'),
                'DateClosed': '',
                'Reason': '',
                'CollateralValue': '',
                'CollateralType': '',
                'History48Months': history(24, pay_status),
            },
            {
                'seq': '2',
                'AccountNumber': f"XXXXXXXXXXXX{(seed * 7) % 10000:04d}",
                'Institution': 'SBI Cards and Payment Services Limited',
                'AccountType': 'Credit Card',
                'OwnershipType': 'Individual',
                'Open': 'Yes',
                'AccountStatus': 'Current Account',
                'Balance': str(10000 + (seed % 6) * 3000),
                'PastDueAmount': '0',
                'LastPayment': '',
                'LastPaymentDate': '',
                'SanctionAmount': '',
                'CreditLimit': '80000',
                'InterestRate': '',
                'RepaymentTenure': '',
                'TermFrequency': 'Monthly',
                'MonthlyPaymentAmount': '',
                'WriteOffAmount': '',
                'AssetClassification': '',
                'DisputeCode': '',
                'SuitFiledStatus': '',
                'DateOpened': f"{opened_year + 1}-01-20",
                'DateReported': today.strftime('%Y-%m-%d'),
                'DateClosed': '',
                'Reason': '',
                'CollateralValue': '',
                'CollateralType': '',
                'History48Months': history(24, '000'),
            },
            {
                'seq': '3',
                'AccountNumber': f"XXXXXXXXXX{(seed * 13) % 10000:04d}",
                'Institution': 'IDFC FIRST Bank Limited',
                'AccountType': 'Consumer Loan',
                'OwnershipType': 'Individual',
                'Open': 'No',
                'AccountStatus': 'Closed Account',
                'Balance': '0',
                'PastDueAmount': '0',
                'LastPayment': '603',
                'LastPaymentDate': f"{opened_year + 2}-07-01",
                'SanctionAmount': '5000',
                'CreditLimit': '',
                'InterestRate': '',
                'RepaymentTenure': '36',
                'TermFrequency': 'Monthly',
                'MonthlyPaymentAmount': '',
                'WriteOffAmount': '',
                'AssetClassification': '',
                'DisputeCode': '',
                'SuitFiledStatus': '',
                'DateOpened': f"{opened_year}-05-29",
                'DateReported': f"{opened_year + 3}-04-16",
                'DateClosed': f"{opened_year + 3}-04-16",
                'Reason': 'Closed Account',
                'CollateralValue': '',
                'CollateralType': '',
                'History48Months': history(12, 'CLSD'),
            },
        ]
        total_balance = sum(int(a['Balance']) for a in accounts)
        cir_data = {
            'IDAndContactInfo': {
                'PersonalInfo': {
                    'Name': {'FullName': str(name or '').upper()},
                    'DateOfBirth': f'{today.year - 25 - (seed % 15)}-01-01',
                    'Age': {'Age': 25 + (seed % 15)},
                    'Gender': (SurepassCreditService._normalize_gender(gender) or 'male').capitalize(),
                    'TotalIncome': 'None',
                    'Occupation': 'SALARIED',
                },
                'IdentityInfo': {
                    'PANId': [{'seq': '1', 'IdNumber': pan}],
                    'VoterID': [{'seq': '1', 'IdNumber': ''}],
                    'NationalIDCard': [{'seq': '1', 'IdNumber': f"5005{seed % 100000000:08d}"}],
                },
                'PhoneInfo': [
                    {'seq': '1', 'typeCode': 'M', 'Number': str(mobile or ''), 'ReportedDate': today.strftime('%Y-%m-%d')},
                ],
                'EmailAddressInfo': [
                    {'seq': '1', 'EmailAddress': f"mock{seed % 1000}@example.com", 'ReportedDate': today.strftime('%Y-%m-%d')},
                ],
                'AddressInfo': [
                    {'seq': '1', 'Address': '12/91, Mock Street, Test Nagar, Kolkata', 'State': 'WB', 'Postal': '700128', 'Type': 'Permanent', 'ReportedDate': today.strftime('%Y-%m-%d')},
                    {'seq': '2', 'Address': '1st Floor, Demo Road, Near Test Market', 'State': 'WB', 'Postal': '700126', 'Type': 'Office', 'ReportedDate': today.strftime('%Y-%m-%d')},
                ],
            },
            'RetailAccountsSummary': {
                'NoOfAccounts': str(len(accounts)),
                'NoOfActiveAccounts': str(sum(1 for a in accounts if a['Open'] == 'Yes')),
                'NoOfWriteOffs': '0',
                'NoOfPastDueAccounts': '1' if is_bad else '0',
                'NoOfZeroBalanceAccounts': '1',
                'RecentAccount': f"Credit Card on {accounts[1]['DateOpened']}",
                'OldestAccount': f"Consumer Loan on {accounts[2]['DateOpened']}",
                'MostSevereStatusWithIn24Months': 'Delinquent' if is_bad else 'Std',
                'SingleHighestBalance': str(balance),
                'SingleHighestCredit': str(sanction),
                'SingleHighestSanctionAmount': str(sanction),
                'AverageOpenBalance': str(total_balance // max(1, len(accounts))),
                'TotalPastDue': accounts[0]['PastDueAmount'] if is_bad else '0.00',
                'TotalCreditLimit': '80000',
                'TotalHighCredit': str(sanction + 80000),
                'TotalSanctionAmount': str(sanction + 5000),
                'TotalBalanceAmount': str(total_balance),
                'TotalMonthlyPaymentAmount': str(emi),
            },
            'RetailAccountDetails': accounts,
            'ScoreDetails': [{
                'Type': 'ERS',
                'Version': '4.0',
                'Name': 'ERS4.0',
                'Value': str(score),
                'ScoringElements': [
                    {'type': 'RES', 'seq': '1', 'Description': 'Total Utilization'},
                    {'type': 'RES', 'seq': '2', 'Description': 'Non Retail Trades'},
                    {'type': 'RES', 'seq': '3', 'Description': 'Total Credit Exposure'},
                ],
            }],
            'Enquiries': [
                {'seq': '1', 'Institution': 'MOCK NBFC', 'Date': f"{today.year}-{max(1, today.month - 2):02d}-10", 'RequestPurpose': 'Personal Loan', 'Amount': '100000'},
            ],
            'EnquirySummary': {
                'Purpose': 'ALL', 'Total': '4', 'Past30Days': '0',
                'Past12Months': '1', 'Past24Months': '2',
                'Recent': f"{today.year}-{max(1, today.month - 2):02d}-10",
            },
            'RecentActivities': {
                'TotalInquiries': '0', 'AccountsOpened': '0',
                'AccountsUpdated': str(len(accounts)), 'AccountsDeliquent': '1' if is_bad else '0',
            },
        }
        return {
            'mock': True,
            'message': f'Mock {bureau.upper()} report (Surepass sandbox mock mode).',
            'data': {
                'client_id': f'mock_{pan.lower()}',
                'name': str(name or '').upper(),
                'pan': pan,
                'mobile': str(mobile or ''),
                'gender': SurepassCreditService._normalize_gender(gender) or 'male',
                'credit_score': str(score),
                'credit_report': {
                    'CCRResponse': {
                        'CIRReportDataLst': [{'CIRReportData': cir_data}],
                    },
                },
            },
        }

    @staticmethod
    def _extract_score(data):
        """Pull the numeric score out of a Surepass response (Equifax v2 / CIBIL)."""
        if not isinstance(data, dict):
            return None
        body = data.get('data') if isinstance(data.get('data'), dict) else data
        raw = body.get('credit_score') or body.get('score') or body.get('cibil_score')
        if raw in (None, '', 'NA', 'N/A'):
            # Fall back to scores array inside the full credit report
            reports = body.get('credit_report')
            if isinstance(reports, list):
                for report in reports:
                    for score_entry in (report or {}).get('scores', []) or []:
                        raw = (score_entry or {}).get('score')
                        if raw not in (None, '', 'NA', 'N/A'):
                            break
                    if raw not in (None, '', 'NA', 'N/A'):
                        break
            elif isinstance(reports, dict):
                # Equifax CCR: ScoreDetails inside CIRReportData
                ccr = reports.get('CCRResponse') or {}
                for item in ccr.get('CIRReportDataLst') or []:
                    cir = (item or {}).get('CIRReportData') or {}
                    for score_entry in cir.get('ScoreDetails') or []:
                        raw = (score_entry or {}).get('Value')
                        if raw not in (None, '', 'NA', 'N/A'):
                            break
                    if raw not in (None, '', 'NA', 'N/A'):
                        break
        try:
            return int(float(str(raw).strip()))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_payload(name, pan, mobile_10, gender=None, bureau='equifax'):
        """Build Surepass request body. Equifax v2 uses id_number/id_type."""
        gender_norm = SurepassCreditService._normalize_gender(gender)
        if bureau == 'equifax':
            payload = {
                'name': ' '.join(str(name or '').strip().split()),
                'id_number': pan,
                'id_type': 'pan',
                'mobile': mobile_10,
                'consent': 'Y',
            }
            if gender_norm:
                payload['gender'] = gender_norm
            return payload
        payload = {
            'name': ' '.join(str(name or '').strip().split()),
            'pan': pan,
            'mobile': mobile_10,
            'consent': 'Y',
        }
        if gender_norm:
            payload['gender'] = gender_norm
        return payload

    @staticmethod
    def fetch_credit_report(name, pan, mobile, gender=None, bureau='cibil'):
        """Fetch a credit report/score from Surepass for the given bureau.

        bureau: 'cibil' or 'equifax'.
        Equifax uses credit-report-v2 (production docs).

        Returns a dict:
            {'status': 'success', 'score': int|None, 'data': raw_response}
            {'status': 'error', 'message': str, 'data': raw_response|None}
        """
        bureau = str(bureau or 'cibil').strip().lower()
        SurepassCreditService._sync_cached_config()
        endpoint = SurepassCreditService._get_endpoint(bureau)
        pan = str(pan or '').strip().upper()
        mobile_10 = SurepassCreditService._normalize_mobile(mobile)
        api_token = SurepassCreditService._get_api_token()
        base_url = SurepassCreditService._get_base_url()
        timeout = SurepassCreditService._get_timeout()

        if SurepassCreditService._is_mock():
            score = SurepassCreditService._mock_score(pan)
            return {
                'status': 'success',
                'score': score,
                'data': SurepassCreditService._mock_full_report(name, pan, mobile_10 or mobile, gender, score, bureau),
            }

        if not pan or not mobile_10 or not name:
            return {'status': 'error', 'message': 'PAN, mobile and name are required for a credit check.', 'data': None}

        if not api_token:
            return {
                'status': 'error',
                'message': 'SUREPASS_API_TOKEN is empty. Set a Production token in .env.',
                'data': None,
            }

        url = f"{base_url}{endpoint}"
        payload = SurepassCreditService._build_payload(name, pan, mobile_10, gender, bureau=bureau)
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
        }
        try:
            identity = SurepassCreditService._token_identity_hint(api_token)
            print(
                f"[Surepass {bureau.upper()}] POST {url} for PAN {pan[:4]}****** "
                f"(token_len={len(api_token)}"
                f"{', identity=' + identity if identity else ''})"
            )
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            data = _safe_json(response)
            print(f"[Surepass {bureau.upper()}] Status: {response.status_code}")
            if response.status_code == 200 and isinstance(data, dict) and data.get('success', True) and data.get('status') != 'error':
                score = SurepassCreditService._extract_score(data)
                return {'status': 'success', 'score': score, 'data': data}

            # Prefer structured Surepass / helper messages over raw HTML dumps.
            error_msg = None
            if isinstance(data, dict):
                error_msg = data.get('message') or data.get('error')
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get('message') or str(error_msg)
            if not error_msg:
                error_msg = f'Status: {response.status_code}'
            if response.status_code == 404:
                error_msg = (
                    f'{bureau.upper()} API path not found on Surepass '
                    f'({url}). Confirm SUREPASS_API_BASE_URL and '
                    f'SUREPASS_{bureau.upper()}_ENDPOINT in .env.'
                )
            elif response.status_code == 401:
                msg_l = str(error_msg).lower()
                if 'whitelist' in msg_l:
                    error_msg = (
                        'Surepass IP not whitelisted. Add this server public IP in '
                        'Surepass console, then retry.'
                    )
                else:
                    hint = ''
                    if identity and str(identity).lower().startswith('dev.'):
                        hint = (
                            ' Your token identity looks like a sandbox/dev token '
                            f'("{identity}"). Production URL needs a Production API token '
                            'from https://console.surepass.app/ (not a sandbox/dev token).'
                        )
                    elif identity:
                        hint = f' Token identity: {identity}.'
                    error_msg = (
                        f'{error_msg}.{hint} '
                        'Copy a fresh Production bearer token into SUREPASS_API_TOKEN and restart.'
                    )
            return {
                'status': 'error',
                'message': f'Surepass {bureau.upper()} check failed ({error_msg})',
                'data': data if isinstance(data, dict) else None,
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'data': None}

    @staticmethod
    def fetch_cibil_report(name, pan, mobile, gender=None):
        return SurepassCreditService.fetch_credit_report(name, pan, mobile, gender, bureau='cibil')

    @staticmethod
    def fetch_equifax_report(name, pan, mobile, gender=None):
        return SurepassCreditService.fetch_credit_report(name, pan, mobile, gender, bureau='equifax')


# ---------------------------------------------------------------------------
# Pre-application check (Equifax) — run from the new-application form,
# stored unattached and linked to the loan when the application is submitted.
# ---------------------------------------------------------------------------

def get_precheck_validity_days():
    try:
        return int(os.getenv('CREDIT_PRECHECK_VALID_DAYS', '30'))
    except (TypeError, ValueError):
        return 30


PENDING_PRECHECK_SESSION_KEY = 'pending_credit_precheck'


def run_pre_application_credit_check(name, pan, mobile, gender=None, fetched_by='pre_application'):
    """Run an Equifax check before any loan application exists — WITHOUT
    saving anything to the database.

    The result is returned as a plain dict (JSON-serializable, suitable for
    storing in the session). It is persisted as a CreditBureauCheck only when
    the loan application is actually submitted (save_pending_precheck_for_loan).
    Returns (payload|None, error_message|None).
    """
    try:
        from django.utils import timezone

        pan = str(pan or '').strip().upper()
        if not pan or not re.match(r'^[A-Z]{5}\d{4}[A-Z]$', pan):
            return None, 'A valid PAN number is required for the credit check.'
        if not str(name or '').strip():
            return None, 'Full name is required for the credit check.'
        if not SurepassCreditService._normalize_mobile(mobile):
            return None, 'A valid 10-digit mobile number is required for the credit check.'

        result = SurepassCreditService.fetch_equifax_report(
            name=name, pan=pan, mobile=mobile, gender=gender
        )

        if result.get('status') == 'success':
            score = result.get('score')
            check_status = 'success' if score is not None else 'no_history'
            remarks = None
        else:
            score = None
            check_status = 'failed'
            remarks = result.get('message')

        payload = {
            'bureau': 'Equifax (Surepass)',
            'pan_number': pan,
            'score': score,
            'status': check_status,
            'decision': classify_score(score) if check_status == 'success' else 'manual_review',
            'remarks': remarks,
            'raw_response': result.get('data'),
            'fetched_by': str(fetched_by or 'pre_application')[:100],
            'fetched_at': timezone.now().isoformat(),
        }
        print(f"[Equifax Pre-Check] Result for PAN {pan[:4]}****** (not saved yet): "
              f"score={score}, status={check_status}, decision={payload['decision']}")
        if check_status == 'failed':
            return payload, remarks or 'Credit check failed.'
        return payload, None
    except Exception as e:
        logger.exception("[Equifax Pre-Check] failed: %s", e)
        return None, 'Credit check service is unavailable. Please try again.'


def serialize_transient_check(payload):
    """Same shape as serialize_credit_check(), but for a not-yet-saved
    pre-check payload dict. Returns None if payload is None."""
    if not payload:
        return None
    policy = get_cibil_policy()
    result = {
        'id': None,
        'bureau': payload.get('bureau'),
        'score': payload.get('score'),
        'status': payload.get('status'),
        'decision': payload.get('decision'),
        'remarks': payload.get('remarks'),
        'fetched_by': payload.get('fetched_by'),
        'fetched_at': payload.get('fetched_at'),
        'min_score': policy['min_score'],
        'review_score': policy['review_score'],
        'enforced': policy['enforce'],
    }
    if payload.get('raw_response') and payload.get('status') != 'failed':
        report = summarize_credit_report(payload['raw_response'])
        if report:
            result['report'] = report
    return result


def save_pending_precheck_for_loan(loan_application, session):
    """Persist the pending pre-check held in the session, linked to the newly
    submitted loan application. Only saves if the PAN matches the customer and
    the check is still within the validity window. Returns the created
    CreditBureauCheck or None. Never raises.
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        from django.utils.dateparse import parse_datetime
        from loan.models import CreditBureauCheck

        if session is None:
            return None
        payload = session.get(PENDING_PRECHECK_SESSION_KEY)
        if not isinstance(payload, dict):
            return None

        customer = getattr(loan_application, 'customer', None)
        customer_pan = (getattr(customer, 'pan_number', None) or '').strip().upper()
        if not customer_pan or payload.get('pan_number') != customer_pan:
            # Pending check belongs to a different customer — keep it for later.
            return None

        fetched_at = parse_datetime(payload.get('fetched_at') or '')
        if fetched_at and fetched_at < timezone.now() - timedelta(days=get_precheck_validity_days()):
            session.pop(PENDING_PRECHECK_SESSION_KEY, None)
            return None

        check = CreditBureauCheck.objects.create(
            loan_application=loan_application,
            customer=customer,
            bureau=payload.get('bureau') or 'Equifax (Surepass)',
            pan_number=payload.get('pan_number'),
            score=payload.get('score'),
            status=payload.get('status') or 'failed',
            decision=payload.get('decision') or 'manual_review',
            remarks=payload.get('remarks'),
            raw_response=payload.get('raw_response'),
            fetched_by=payload.get('fetched_by') or 'pre_application',
        )
        # Preserve the actual bureau-pull timestamp (auto_now_add set it to now).
        if fetched_at:
            CreditBureauCheck.objects.filter(pk=check.pk).update(fetched_at=fetched_at)

        session.pop(PENDING_PRECHECK_SESSION_KEY, None)
        if hasattr(session, 'modified'):
            session.modified = True
        print(f"[Equifax Pre-Check] Saved check #{check.id} (score={check.score}) "
              f"for {loan_application.loan_ref_no} at submission.")
        return check
    except Exception as e:
        logger.warning("[Equifax Pre-Check] save_pending_precheck_for_loan failed: %s", e)
        return None


def attach_precheck_to_loan(loan_application):
    """Link the most recent unattached pre-application check (matching the
    customer's PAN, within the validity window) to this loan application.

    Returns the linked check or None. Never raises.
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        from loan.models import CreditBureauCheck

        customer = loan_application.customer
        pan = (getattr(customer, 'pan_number', None) or '').strip().upper()
        if not pan:
            return None

        cutoff = timezone.now() - timedelta(days=get_precheck_validity_days())
        check = (
            CreditBureauCheck.objects
            .filter(loan_application__isnull=True, pan_number=pan, fetched_at__gte=cutoff)
            .order_by('-fetched_at')
            .first()
        )
        if not check:
            return None

        check.loan_application = loan_application
        if check.customer_id is None:
            check.customer = customer
            check.save(update_fields=['loan_application', 'customer'])
        else:
            check.save(update_fields=['loan_application'])
        print(f"[Equifax Pre-Check] Linked check #{check.id} (score={check.score}) to {loan_application.loan_ref_no}")
        return check
    except Exception as e:
        logger.warning("[Equifax Pre-Check] attach_precheck_to_loan failed: %s", e)
        return None


def handle_credit_check_on_submit(loan_application, session=None):
    """Called after a loan application is submitted.

    Persists the pending pre-application Equifax check from the session (the
    check is NOT stored in the database at check time — only here, once the
    application actually exists). Falls back to linking a legacy unattached
    DB row (matched by PAN) if no pending session check applies.
    No automatic bureau pull happens at submission time. Never raises.
    """
    try:
        saved = save_pending_precheck_for_loan(loan_application, session)
        if not saved:
            attach_precheck_to_loan(loan_application)
    except Exception as e:
        logger.warning("[Credit Check] handle_credit_check_on_submit failed for %s: %s",
                       getattr(loan_application, 'loan_ref_no', '?'), e)


# ---------------------------------------------------------------------------
# Loan application integration
# ---------------------------------------------------------------------------

def find_saved_credit_check(loan_application):
    """Return the latest usable saved credit check for this loan's customer,
    without calling the bureau API.

    Looks for checks (any bureau) that are either linked to this loan, linked
    to the same customer (e.g. from an earlier application), or unattached
    pre-application checks matching the customer's PAN. Failed checks are
    ignored. Returns a CreditBureauCheck or None. Never raises.
    """
    try:
        from django.db.models import Q
        from loan.models import CreditBureauCheck

        q = Q(loan_application=loan_application)
        customer = getattr(loan_application, 'customer', None)
        if customer:
            q |= Q(customer=customer)
            pan = (getattr(customer, 'pan_number', None) or '').strip().upper()
            if pan:
                q |= Q(pan_number=pan)

        return (
            CreditBureauCheck.objects
            .filter(q, status__in=['success', 'no_history'])
            .order_by('-fetched_at')
            .first()
        )
    except Exception as e:
        logger.warning("find_saved_credit_check failed for %s: %s",
                       getattr(loan_application, 'loan_ref_no', '?'), e)
        return None


def run_credit_check_for_loan(loan_ref_no, fetched_by='manual'):
    """Fetch and persist an Equifax check for an existing loan application.

    Used by the manual fetch on the branch application detail page.
    Returns the created CreditBureauCheck instance, or None on any failure.
    Never raises.
    """
    try:
        from loan.models import LoanApplication, CreditBureauCheck

        loan_app = (
            LoanApplication.objects.select_related('customer')
            .filter(loan_ref_no=loan_ref_no)
            .first()
        )
        if not loan_app or not loan_app.customer:
            logger.warning("[Equifax] Loan application or customer not found for %s", loan_ref_no)
            return None

        customer = loan_app.customer
        if not customer.pan_number:
            logger.info("[Equifax] No PAN for customer %s; skipping credit check.", customer.customer_id)
            return None

        result = SurepassCreditService.fetch_equifax_report(
            name=customer.full_name,
            pan=customer.pan_number,
            mobile=customer.contact,
            gender=customer.gender,
        )

        if result.get('status') == 'success':
            score = result.get('score')
            check_status = 'success' if score is not None else 'no_history'
            remarks = None
        else:
            score = None
            check_status = 'failed'
            remarks = result.get('message')

        check = CreditBureauCheck.objects.create(
            loan_application=loan_app,
            customer=customer,
            bureau='Equifax (Surepass)',
            pan_number=customer.pan_number,
            score=score,
            status=check_status,
            decision=classify_score(score) if check_status == 'success' else 'manual_review',
            remarks=remarks,
            raw_response=result.get('data'),
            fetched_by=str(fetched_by or 'auto_on_submit')[:100],
        )
        print(f"[Equifax] Check saved for {loan_ref_no}: score={score}, status={check_status}, decision={check.decision}")
        return check
    except Exception as e:
        logger.exception("[Equifax] run_credit_check_for_loan failed for %s: %s", loan_ref_no, e)
        return None


def _clean_value(value):
    """Bureau responses use '-1' / 'NA' for not-applicable values."""
    if value in (None, '', '-1', -1, 'NA', 'N/A'):
        return None
    return value


def _first_id_number(identity_info, key):
    """Equifax IdentityInfo values are lists like [{'IdNumber': 'X'}] (or a dict/str)."""
    val = (identity_info or {}).get(key)
    if isinstance(val, list) and val:
        val = val[0]
    if isinstance(val, dict):
        return _clean_value(val.get('IdNumber'))
    return _clean_value(val)


def _parse_equifax_ccr(body):
    """Parse the Equifax IDCR (CCRResponse) structure returned by Surepass."""
    report = body.get('credit_report')
    if isinstance(report, list):
        report = report[0] if report else {}
    if not isinstance(report, dict):
        return None
    ccr = report.get('CCRResponse') or {}
    cir_list = ccr.get('CIRReportDataLst') or []
    if not cir_list:
        return None
    # Prefer the CIR block that has retail/score detail (IDCR); else first non-empty.
    data = {}
    for item in cir_list:
        candidate = (item or {}).get('CIRReportData') or {}
        if not candidate:
            continue
        if (
            candidate.get('RetailAccountDetails')
            or candidate.get('RetailAccountsSummary')
            or candidate.get('ScoreDetails')
        ):
            data = candidate
            break
        if not data:
            data = candidate
    if not data:
        return None

    idc = data.get('IDAndContactInfo') or {}
    pi = idc.get('PersonalInfo') or {}
    name_obj = pi.get('Name') or {}
    age_obj = pi.get('Age') or {}
    identity = idc.get('IdentityInfo') or {}

    personal = {
        'name': _clean_value(name_obj.get('FullName')) or _clean_value(body.get('name')),
        'date_of_birth': _clean_value(pi.get('DateOfBirth')),
        'age': _clean_value(age_obj.get('Age')),
        'gender': _clean_value(pi.get('Gender')) or _clean_value(body.get('gender')),
        'total_income': _clean_value(pi.get('TotalIncome')),
        'occupation': _clean_value(pi.get('Occupation')),
    }

    identification = {
        'pan': _first_id_number(identity, 'PANId') or _clean_value(body.get('pan')),
        'voter_id': _first_id_number(identity, 'VoterID'),
        'passport': _first_id_number(identity, 'PassportId') or _first_id_number(identity, 'PassportID'),
        'uid': _first_id_number(identity, 'NationalIDCard') or _first_id_number(identity, 'UIDId'),
        'driver_license': _first_id_number(identity, 'DriverLicense'),
        'other_id': _first_id_number(identity, 'OtherId'),
    }

    phones = []
    for ph in idc.get('PhoneInfo') or []:
        ph = ph or {}
        number = _clean_value(ph.get('Number'))
        if number:
            phones.append({
                'number': number,
                'type': _clean_value(ph.get('typeCode')) or _clean_value(ph.get('PhoneType')),
                'reported_date': _clean_value(ph.get('ReportedDate')),
            })

    emails = []
    for em in idc.get('EmailAddressInfo') or []:
        em = em or {}
        address = _clean_value(em.get('EmailAddress'))
        if address:
            emails.append({'email': address, 'reported_date': _clean_value(em.get('ReportedDate'))})

    addresses = []
    for addr in idc.get('AddressInfo') or []:
        addr = addr or {}
        text = _clean_value(addr.get('Address'))
        if text:
            addresses.append({
                'address': text,
                'state': _clean_value(addr.get('State')),
                'postal': _clean_value(addr.get('Postal')),
                'type': _clean_value(addr.get('Type')),
                'reported_date': _clean_value(addr.get('ReportedDate')),
            })

    score_details = data.get('ScoreDetails') or []
    score_entry = score_details[0] if score_details else {}
    factors = []
    for el in (score_entry.get('ScoringElements') or []):
        desc = _clean_value((el or {}).get('Description'))
        if desc:
            factors.append(desc)
    score = {
        'value': _clean_value(score_entry.get('Value')) or _clean_value(body.get('credit_score')),
        'name': _clean_value(score_entry.get('Name')),
        'type': _clean_value(score_entry.get('Type')),
        'version': _clean_value(score_entry.get('Version')),
        'factors': factors,
    }

    rs = data.get('RetailAccountsSummary') or {}
    account_summary = {
        'no_of_accounts': _clean_value(rs.get('NoOfAccounts')),
        'active_accounts': _clean_value(rs.get('NoOfActiveAccounts')),
        'write_offs': _clean_value(rs.get('NoOfWriteOffs')),
        'past_due_accounts': _clean_value(rs.get('NoOfPastDueAccounts')),
        'zero_balance_accounts': _clean_value(rs.get('NoOfZeroBalanceAccounts')),
        'recent_account': _clean_value(rs.get('RecentAccount')),
        'oldest_account': _clean_value(rs.get('OldestAccount')),
        'most_severe_status_24m': _clean_value(rs.get('MostSevereStatusWithIn24Months')),
        'single_highest_balance': _clean_value(rs.get('SingleHighestBalance')),
        'single_highest_credit': _clean_value(rs.get('SingleHighestCredit')),
        'single_highest_sanction': _clean_value(rs.get('SingleHighestSanctionAmount')),
        'average_open_balance': _clean_value(rs.get('AverageOpenBalance')),
        'total_past_due': _clean_value(rs.get('TotalPastDue')),
        'total_credit_limit': _clean_value(rs.get('TotalCreditLimit')),
        'total_high_credit': _clean_value(rs.get('TotalHighCredit')),
        'total_sanction': _clean_value(rs.get('TotalSanctionAmount')),
        'total_balance': _clean_value(rs.get('TotalBalanceAmount')),
        'total_monthly_payment': _clean_value(rs.get('TotalMonthlyPaymentAmount')),
    }

    accounts = []
    for acc in data.get('RetailAccountDetails') or []:
        acc = acc or {}
        history = []
        for h in acc.get('History48Months') or []:
            h = h or {}
            history.append({
                'month': _clean_value(h.get('key')),
                'status': _clean_value(h.get('PaymentStatus')),
                'suit_filed': _clean_value(h.get('SuitFiledStatus')),
                'asset_class': _clean_value(h.get('AssetClassificationStatus')),
            })
        accounts.append({
            'account_number': _clean_value(acc.get('AccountNumber')),
            'institution': _clean_value(acc.get('Institution')),
            'account_type': _clean_value(acc.get('AccountType')),
            'ownership': _clean_value(acc.get('OwnershipType')),
            'open': _clean_value(acc.get('Open')),
            'account_status': _clean_value(acc.get('AccountStatus')),
            'balance': _clean_value(acc.get('Balance')),
            'past_due_amount': _clean_value(acc.get('PastDueAmount')),
            'last_payment': _clean_value(acc.get('LastPayment')),
            'last_payment_date': _clean_value(acc.get('LastPaymentDate')),
            'sanction_amount': _clean_value(acc.get('SanctionAmount')),
            'credit_limit': _clean_value(acc.get('CreditLimit')),
            'interest_rate': _clean_value(acc.get('InterestRate')),
            'repayment_tenure': _clean_value(acc.get('RepaymentTenure')),
            'term_frequency': _clean_value(acc.get('TermFrequency')),
            'monthly_payment': _clean_value(acc.get('MonthlyPaymentAmount')),
            'writeoff_amount': _clean_value(acc.get('WriteOffAmount')),
            'asset_classification': _clean_value(acc.get('AssetClassification')),
            'dispute_code': _clean_value(acc.get('DisputeCode')),
            'suit_filed_status': _clean_value(acc.get('SuitFiledStatus')),
            'date_opened': _clean_value(acc.get('DateOpened')),
            'date_reported': _clean_value(acc.get('DateReported')),
            'date_closed': _clean_value(acc.get('DateClosed')),
            'reason': _clean_value(acc.get('Reason')),
            'collateral_value': _clean_value(acc.get('CollateralValue')),
            'collateral_type': _clean_value(acc.get('CollateralType')),
            'payment_history': history,
        })

    ra = data.get('RecentActivities') or {}
    recent_activity = {
        'total_inquiries': _clean_value(ra.get('TotalInquiries')),
        'accounts_opened': _clean_value(ra.get('AccountsOpened')),
        'accounts_updated': _clean_value(ra.get('AccountsUpdated')),
        'accounts_delinquent': _clean_value(ra.get('AccountsDeliquent')) or _clean_value(ra.get('AccountsDelinquent')),
    }

    enquiries = []
    for enq in data.get('Enquiries') or []:
        enq = enq or {}
        enquiries.append({
            'institution': _clean_value(enq.get('Institution')),
            'date': _clean_value(enq.get('Date')),
            'purpose': _clean_value(enq.get('RequestPurpose')) or _clean_value(enq.get('Purpose')),
            'amount': _clean_value(enq.get('Amount')),
        })

    enq_summary_raw = data.get('EnquirySummary') or {}
    enquiry_summary = {
        'purpose': _clean_value(enq_summary_raw.get('Purpose')),
        'total': _clean_value(enq_summary_raw.get('Total')),
        'past_30_days': _clean_value(enq_summary_raw.get('Past30Days')),
        'past_12_months': _clean_value(enq_summary_raw.get('Past12Months')),
        'past_24_months': _clean_value(enq_summary_raw.get('Past24Months')),
        'recent': _clean_value(enq_summary_raw.get('Recent')),
    }

    return {
        'personal': personal,
        'identification': identification,
        'phones': phones,
        'emails': emails,
        'addresses': addresses,
        'score': score,
        'account_summary': account_summary,
        'accounts': accounts,
        'recent_activity': recent_activity,
        'enquiries': enquiries,
        'enquiry_summary': enquiry_summary,
    }


def _parse_cibil_style(body):
    """Fallback parser for CIBIL-style payloads (names/accounts/enquiries lists),
    mapped into the same normalized structure as the Equifax parser."""
    reports = body.get('credit_report')
    if isinstance(reports, list) and reports:
        report = reports[0] or {}
    elif isinstance(reports, dict):
        report = reports
    else:
        report = {}

    names = report.get('names') or []
    first_name_entry = names[0] if names else {}
    score_entries = report.get('scores') or []
    score_entry = score_entries[0] if score_entries else {}

    pan = _clean_value(body.get('pan'))
    if not pan:
        for id_entry in report.get('ids') or []:
            if (id_entry or {}).get('idType') == 'TaxId':
                pan = _clean_value(id_entry.get('idNumber'))
                break

    phones = []
    for tel in report.get('telephones') or []:
        number = _clean_value((tel or {}).get('telephoneNumber'))
        if number:
            phones.append({'number': number, 'type': _clean_value((tel or {}).get('telephoneType')), 'reported_date': None})
    if not phones and _clean_value(body.get('mobile')):
        phones.append({'number': body.get('mobile'), 'type': None, 'reported_date': None})

    emails = []
    for em in report.get('emails') or []:
        address = _clean_value((em or {}).get('emailID'))
        if address:
            emails.append({'email': address, 'reported_date': None})

    addresses = []
    for addr in report.get('addresses') or []:
        addr = addr or {}
        parts = [addr.get('line1'), addr.get('line2')]
        text = ', '.join(str(p).strip() for p in parts if _clean_value(p))
        if text:
            addresses.append({
                'address': text,
                'state': _clean_value(addr.get('stateCode')),
                'postal': _clean_value(addr.get('pinCode')),
                'type': _clean_value(addr.get('addressCategory')),
                'reported_date': _clean_value(addr.get('dateReported')),
            })

    summary_resp = ((report.get('response') or {}).get('consumerSummaryresp') or {})
    acc_summary = summary_resp.get('accountSummary') or {}
    inq_summary = summary_resp.get('inquirySummary') or {}

    accounts = []
    for acc in report.get('accounts') or []:
        acc = acc or {}
        history = []
        for m in acc.get('monthlyPayStatus') or []:
            m = m or {}
            history.append({
                'month': _clean_value((m.get('date') or '')[:7]),
                'status': _clean_value(m.get('status')),
                'suit_filed': None,
                'asset_class': None,
            })
        accounts.append({
            'account_number': _clean_value(acc.get('accountNumber')),
            'institution': _clean_value(acc.get('memberShortName')),
            'account_type': _clean_value(acc.get('accountType')),
            'ownership': _clean_value(acc.get('ownershipIndicator')),
            'open': 'No' if _clean_value(acc.get('dateClosed')) else 'Yes',
            'account_status': _clean_value(acc.get('creditFacilityStatus')),
            'balance': _clean_value(acc.get('currentBalance')),
            'past_due_amount': _clean_value(acc.get('amountOverdue')),
            'last_payment': _clean_value(acc.get('actualPaymentAmount')),
            'last_payment_date': _clean_value(acc.get('lastPaymentDate')),
            'sanction_amount': _clean_value(acc.get('highCreditAmount')),
            'credit_limit': None,
            'interest_rate': None,
            'repayment_tenure': _clean_value(acc.get('termMonths')),
            'term_frequency': _clean_value(acc.get('paymentFrequency')),
            'monthly_payment': _clean_value(acc.get('emiAmount')),
            'writeoff_amount': _clean_value(acc.get('woAmountTotal')),
            'asset_classification': None,
            'dispute_code': None,
            'suit_filed_status': _clean_value(acc.get('suitFiledWillfulDefaultWrittenOff')),
            'date_opened': _clean_value(acc.get('dateOpened')),
            'date_reported': _clean_value(acc.get('dateReported')),
            'date_closed': _clean_value(acc.get('dateClosed')),
            'reason': None,
            'collateral_value': None,
            'collateral_type': None,
            'payment_history': history,
        })

    enquiries = []
    for enq in report.get('enquiries') or []:
        enq = enq or {}
        enquiries.append({
            'institution': _clean_value(enq.get('memberShortName')),
            'date': _clean_value(enq.get('enquiryDate')),
            'purpose': _clean_value(enq.get('enquiryPurpose')),
            'amount': _clean_value(enq.get('enquiryAmount')),
        })

    return {
        'personal': {
            'name': _clean_value(body.get('name')) or _clean_value(first_name_entry.get('name')),
            'date_of_birth': _clean_value(first_name_entry.get('birthDate')),
            'age': None,
            'gender': _clean_value(body.get('gender')) or _clean_value(first_name_entry.get('gender')),
            'total_income': None,
            'occupation': None,
        },
        'identification': {'pan': pan, 'voter_id': None, 'passport': None, 'uid': None, 'driver_license': None, 'other_id': None},
        'phones': phones,
        'emails': emails,
        'addresses': addresses,
        'score': {
            'value': _clean_value(body.get('credit_score')) or _clean_value(score_entry.get('score')),
            'name': _clean_value(score_entry.get('scoreName')),
            'type': None,
            'version': _clean_value(score_entry.get('scoreCardVersion')),
            'factors': [],
        },
        'account_summary': {
            'no_of_accounts': _clean_value(acc_summary.get('totalAccounts')),
            'active_accounts': None,
            'write_offs': None,
            'past_due_accounts': _clean_value(acc_summary.get('overdueAccounts')),
            'zero_balance_accounts': _clean_value(acc_summary.get('zeroBalanceAccounts')),
            'recent_account': _clean_value(acc_summary.get('recentDateOpened')),
            'oldest_account': _clean_value(acc_summary.get('oldestDateOpened')),
            'most_severe_status_24m': None,
            'single_highest_balance': None,
            'single_highest_credit': None,
            'single_highest_sanction': None,
            'average_open_balance': None,
            'total_past_due': _clean_value(acc_summary.get('overdueBalance')),
            'total_credit_limit': None,
            'total_high_credit': _clean_value(acc_summary.get('highCreditAmount')),
            'total_sanction': None,
            'total_balance': _clean_value(acc_summary.get('currentBalance')),
            'total_monthly_payment': None,
        },
        'accounts': accounts,
        'recent_activity': {'total_inquiries': _clean_value(inq_summary.get('totalInquiry')), 'accounts_opened': None, 'accounts_updated': None, 'accounts_delinquent': None},
        'enquiries': enquiries,
        'enquiry_summary': {
            'purpose': 'ALL',
            'total': _clean_value(inq_summary.get('totalInquiry')),
            'past_30_days': _clean_value(inq_summary.get('inquiryPast30Days')),
            'past_12_months': _clean_value(inq_summary.get('inquiryPast12Months')),
            'past_24_months': _clean_value(inq_summary.get('inquiryPast24Months')),
            'recent': _clean_value(inq_summary.get('recentInquiryDate')),
        },
    }


def summarize_credit_report(raw):
    """Extract a display-friendly, IDCR-style structure from a Surepass credit
    report response. Handles the Equifax CCRResponse structure and falls back
    to CIBIL-style payloads. Returns None if there is nothing to show."""
    try:
        if not isinstance(raw, dict):
            return None
        body = raw.get('data') if isinstance(raw.get('data'), dict) else raw

        result = _parse_equifax_ccr(body) or _parse_cibil_style(body)
        if not result:
            return None

        has_content = any([
            (result.get('personal') or {}).get('name'),
            (result.get('score') or {}).get('value'),
            result.get('accounts'),
            result.get('enquiries'),
            result.get('addresses'),
        ])
        if not has_content:
            return None

        result['is_mock'] = bool(raw.get('mock') or body.get('mock'))
        return result
    except Exception as e:
        logger.warning("summarize_credit_report failed: %s", e)
        return None


def serialize_credit_check(check):
    """Compact dict for API responses / templates. Returns None if check is None."""
    if not check:
        return None
    policy = get_cibil_policy()
    result = {
        'id': check.id,
        'bureau': check.bureau,
        'score': check.score,
        'status': check.status,
        'decision': check.decision,
        'remarks': check.remarks,
        'fetched_by': check.fetched_by,
        'fetched_at': check.fetched_at,
        'min_score': policy['min_score'],
        'review_score': policy['review_score'],
        'enforced': policy['enforce'],
    }
    if check.raw_response and check.status != 'failed':
        report = summarize_credit_report(check.raw_response)
        if report:
            result['report'] = report
    return result
