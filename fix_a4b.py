fp = 'backend/test_dzmi_diag.py'
c = open(fp, 'r', encoding='utf-8').read()
old = '''client = MongoClient(
    "mongodb+srv://ahatesamahamed_db_user:Aew8XBwyjZm2sJGR@cluster0.w9o56pq.mongodb.net/bioguard_research?retryWrites=true&w=majority",
    serverSelectionTimeoutMS=10000
)'''
new = '''client = MongoClient(
    os.getenv("MONGO_URI", ""),
    serverSelectionTimeoutMS=10000
)'''
c = c.replace(old, new, 1)
open(fp, 'w', encoding='utf-8').write(c)
print('FIXED')
