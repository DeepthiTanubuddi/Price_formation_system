import urllib.request, json, re

try:
    html1 = urllib.request.urlopen('https://unsplash.com/photos/1518492104633-130d0cc84637').read().decode('utf-8')
    alt1 = re.search(r'<title>(.*?)</title>', html1)
    print('Image 1 title:', alt1.group(1) if alt1 else 'None')
except Exception as e:
    print('Image 1 error:', e)

try:
    html2 = urllib.request.urlopen('https://unsplash.com/photos/1569288052389-7e8d4a4e3f66').read().decode('utf-8')
    alt2 = re.search(r'<title>(.*?)</title>', html2)
    print('Image 2 title:', alt2.group(1) if alt2 else 'None')
except Exception as e:
    print('Image 2 error:', e)
