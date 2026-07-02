with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find('ZONES')
print(content[idx:idx+500])