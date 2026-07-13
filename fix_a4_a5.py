import os

# ============ A4: Remove hardcoded MongoDB credentials ============

# File 1: dzmi.py
fp = 'backend/data_collectors/dzmi.py'
c = open(fp, 'r', encoding='utf-8').read()
old = '''MONGO_URI = (
    "mongodb+srv://ahatesamahamed_db_user:Aew8XBwyjZm2sJGR"
    "@cluster0.w9o56pq.mongodb.net/bioguard_research"
    "?retryWrites=true&w=majority"
)'''
new = 'MONGO_URI = os.getenv("MONGO_URI")'
c = c.replace(old, new, 1)
# Ensure os is imported
if 'import os' not in c:
    c = 'import os\n' + c
open(fp, 'w', encoding='utf-8').write(c)
print('dzmi.py - credential removed, uses os.getenv')

# File 2: mobility_repository.py
fp = 'backend/data_collectors/mobility_repository.py'
c = open(fp, 'r', encoding='utf-8').read()
old = '''MONGO_URI = (
    "mongodb+srv://ahatesamahamed_db_user:Aew8XBwyjZm2sJGR"
    "@cluster0.w9o56pq.mongodb.net/bioguard_research"
    "?retryWrites=true&w=majority"
)'''
new = 'MONGO_URI = os.getenv("MONGO_URI")'
c = c.replace(old, new, 1)
if 'import os' not in c:
    c = 'import os\n' + c
open(fp, 'w', encoding='utf-8').write(c)
print('mobility_repository.py - credential removed, uses os.getenv')

# File 3: test_dzmi_diag.py
fp = 'backend/test_dzmi_diag.py'
c = open(fp, 'r', encoding='utf-8').read()
old = 'MONGO_URI = "mongodb+srv://ahatesamahamed_db_user:Aew8XBwyjZm2sJGR@cluster0.w9o56pq.mongodb.net/bioguard_research?retryWrites=true&w=majority",'
new = 'MONGO_URI = os.getenv("MONGO_URI", ""),'
c = c.replace(old, new, 1)
if 'import os' not in c:
    c = 'import os\n' + c
open(fp, 'w', encoding='utf-8').write(c)
print('test_dzmi_diag.py - credential removed, uses os.getenv')

print('\nA4 DONE - All 3 files fixed.')

# ============ A5: Update requirements.txt ============

fp = 'backend/requirements.txt'
c = open(fp, 'r', encoding='utf-8').read()

missing = [
    'apscheduler==3.10.4',
    'atproto==0.0.63',
    'feedparser==6.0.11',
    'beautifulsoup4==4.12.3',
    'google-api-python-client==2.140.0',
    'shap==0.45.1',
    'joblib==1.4.2',
    'scipy==1.13.1',
    'lxml==5.2.2',
    'python-dateutil==2.9.0',
]

# Add only what's missing
for pkg in missing:
    name = pkg.split('==')[0].lower().replace('-','_')
    if name not in c.lower().replace('-','_'):
        c += '\n' + pkg

open(fp, 'w', encoding='utf-8').write(c)
print('\nA5 DONE - requirements.txt updated.')
print('\nBOTH TASKS COMPLETE.')
