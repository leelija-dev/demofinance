from django.core.management.base import BaseCommand
from loan.models import ChartOfAccount

class Command(BaseCommand):
    help = 'Seed the database with initial chart of accounts data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding chart of accounts...')
        
        rows = [
            ('A', 1, 'Loan disbursement - daily', '120', 'Loan disbursement for daily collection'),
            ('A', 2, 'Loan disbursement - Group', '121', 'Loan disbursement for weekly collection'),
            ('A', 3, 'Installment collection daily', '122', 'Loan collection on daily basis'),
            ('A', 4, 'Installment collection group', '123', 'Loan collection from group'),
            ('A', 5, 'Bad Loan', '124', ''),
            ('A', 6, 'Furniture and fixture', '130', ''),
            ('A', 7, 'Computer', '131', ''),
            ('A', 8, 'Printer', '132', ''),
            ('A', 9, 'Software Development', '133', ''),
            ('A', 10, 'Equipments', '134', ''),
            ('A', 11, 'Cash in hand', '140', ''),
            ('A', 12, 'Cash at bank', '141', ''),
            ('A', 13, 'UPI Transaction', '142', ''),
            ('A', 14, 'Accounts receivable', '143', ''),
            ('A', 15, 'Advance for purchase & expenses', '144', ''),

            ('B', 1, 'Capital fund', '201', ''),
            ('B', 2, 'Member contribution', '202', ''),
            ('B', 3, 'Term loan', '203', ''),
            ('B', 4, 'Saving deposits', '204', ''),
            ('B', 5, 'Donation', '205', 'Received in advance'),
            ('B', 6, 'Liabilities for expenses', '206', ''),
            ('B', 7, 'Accumulated Depreciation', '207', ''),
            ('B', 8, 'Loan loss reserve', '208', ''),

            ('C', 1, 'Staff salary and benefits', '251', ''),
            ('C', 2, 'Travelling and transportation', '252', ''),
            ('C', 3, 'Office rent', '253', ''),
            ('C', 4, 'Printing and stationery', '254', ''),
            ('C', 5, 'Repair and maintenance', '255', ''),
            ('C', 6, 'Interest on loan', '256', ''),
            ('C', 7, 'Audit & Legal expenses', '257', ''),
            ('C', 8, 'Bank Charges', '258', ''),
            ('C', 9, 'Interest on Saving', '259', ''),
            ('C', 10, 'Electricity', '260', ''),
            ('C', 11, 'Educational activities', '261', ''),
            ('C', 12, 'Health activities', '262', ''),
            ('C', 13, 'Social activities', '263', ''),
            ('C', 14, 'Depreciation expenses', '264', ''),
            ('C', 15, 'Loan loss provision', '265', ''),

            ('D', 1, 'Service Charge realization', '280', ''),
            ('D', 2, 'Loan processing fees', '281', ''),
            ('D', 3, 'Member admission fees', '282', ''),
            ('D', 4, 'Misc. Income', '283', ''),
            ('D', 5, 'Donation', '284', 'Received for the year'),
        ]

        created_count = 0
        updated_count = 0

        for main_type, sl_no, head, code, desc in rows:
            obj, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    'main_type': main_type,
                    'sl_no': sl_no,
                    'head_of_account': head,
                    'description': desc or None,
                    'is_editable': False,  # seeded rows are locked
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded chart of accounts. Created: {created_count}, Updated: {updated_count}'
            )
        )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing records',
        )
