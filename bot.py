import csv, time, urllib.request
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='a' and a.get('href'): self.links.append((a['href'],a.get('rel','')))
def matches(url, domain):
    h=urlparse(url).hostname or ''
    return h==domain or h.endswith('.'+domain)
with open('report.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['source','status','competitor_links','saveitbro_links','rel'])
    for url in dict.fromkeys(open('candidates.txt').read().splitlines()):
        if not url.startswith('https://'): continue
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'SaveItBroLinkAudit/1.0'})
            with urllib.request.urlopen(req,timeout=20) as r:
                p=Links(); p.feed(r.read(2000000).decode('utf-8','replace')); base=r.geturl()
            links=[(urljoin(base,h),rel) for h,rel in p.links]
            own=[(h,rel) for h,rel in links if matches(h,'saveitbro.com')]
            rival=[h for h,rel in links if any(matches(h,d) for d in ['fastdl.app','snapinsta.app','saveinsta.app'])]
            w.writerow([url,'checked',len(set(rival)),len(set(h for h,rel in own)), ';'.join(sorted(set(rel for h,rel in own)))])
        except Exception as e:
            w.writerow([url,'unverified: '+type(e).__name__,'','',''])
        time.sleep(3)
print('Report saved to report.csv')
