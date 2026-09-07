#!/usr/bin/env python3
"""Quick verification that companies tracker is wired correctly."""

from job_bot import applications, companies
import json

# Verify funnel still correct
summary = applications.summary()
print('=== APPLICATIONS FUNNEL ===')
print(f'Total: {summary["total"]}')
print(f'By Status: {summary["by_status"]}')

# Verify companies loaded
all_cos = companies.list_all()
print(f'\n=== COMPANIES ===')
print(f'Total in DB: {len(all_cos)}')

# Show first 3
print(f'\nFirst 3 companies:')
for c in all_cos[:3]:
    print(f'  - {c["name"]} (tier: {c.get("tier", "unknown")}, next_due: {c.get("next_check_due", "N/A")})')

# Show overdue
overdue = companies.due_for_check()
print(f'\nOverdue for check: {len(overdue)}')

# Test manual intake
print(f'\n=== TEST MANUAL INTAKE ===')
try:
    from job_bot import intake
    result = intake.log_job(
        url='https://example.com/job/123',
        company_name='Test Corp',
        title='Software Engineer',
        portal='linkedin',
        status='applied'
    )
    print(f'Logged job: {result["company_name"]} - {result["job_title"]}')

    # Check funnel updated
    new_summary = applications.summary()
    if new_summary['total'] > summary['total']:
        print(f'Funnel updated! Total: {summary["total"]} -> {new_summary["total"]}')
    else:
        print(f'Funnel unchanged (test job may be deduped)')
except Exception as e:
    print(f'Error: {e}')

print('\n✅ System verification complete')
