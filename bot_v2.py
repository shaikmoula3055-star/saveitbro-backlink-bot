"""Bounded discovery on known publisher sites; no submissions."""
import csv, json, time, re, urllib.request, urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from html.parser import HTMLParser
from datetime import datetime, timezone

UA = 'SaveItBroLinkAudit/2.0'
RIVALS = ('fastdl.app','snapinsta.app','saveinsta.app')
TOPIC = re.compile(r'instagram.{0,90}(download|save|backup|tool)|(?:download|save|backup).{0,90}instagram', re.I)
BAD = re.compile(r'casino|gambling|backlink.generator|black.hat|adult|hostingersite|mybluehost', re.I)
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.anchor=None; self.title=''; self.in_title=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='title': self.in_title=True
        if tag=='a' and a.get('href'): self.anchor=[a['href'],a.get('rel') or '', '']
    def handle_data(self, data):
        if self.in_title: self.title+=data
        if self.anchor: self.anchor[2]+=data
    def handle_endtag(self, tag):
        if tag=='title': self.in_title=False
        if tag=='a' and self.anchor: self.links.append(self.anchor); self.anchor=None
def norm(url):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password: return ''
    return urlunsplit(('https',p.netloc.lower(),p.path.rstrip('/') or '/', '', ''))
def host(url):
    return (urlsplit(url).hostname or '').removeprefix('www.')
def match(url, domain):
    h=host(url); return h==domain or h.endswith('.'+domain)
robots={}
def fetch(url, allowed):
    if host(url) not in allowed: raise ValueError('outside approved publisher hosts')
    origin='https://'+urlsplit(url).netloc
    if origin not in robots:
        rp=urllib.robotparser.RobotFileParser(origin+'/robots.txt')
        try:
            with urllib.request.urlopen(urllib.request.Request(rp.url,headers={'User-Agent':UA}),timeout=8) as f:
                rp.parse(f.read(200000).decode('utf-8','replace').splitlines())
        except urllib.error.HTTPError as e:
            if e.code==404: rp.parse([])
            else: raise
        robots[origin]=rp
    if not robots[origin].can_fetch(UA,url): raise ValueError('robots denied')
    time.sleep(max(2,robots[origin].crawl_delay(UA) or 0))
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=12) as f:
        if host(f.geturl()) not in allowed: raise ValueError('external redirect')
        if 'html' not in f.headers.get('Content-Type',''): raise ValueError('not HTML')
        p=Page(); p.feed(f.read(2000000).decode('utf-8','replace'))
        return p,f.geturl()
def main():
    seeds=list(dict.fromkeys(filter(None,(norm(x.strip()) for x in Path('candidates.txt').read_text().splitlines()))))
    allowed={host(x) for x in seeds}
    state=Path('state.json')
    history=json.loads(state.read_text()) if state.exists() else {}
    queue=list(dict.fromkeys(seeds+list(history)))[:25]
    rows=[]; found={}; checked=set()
    for url in queue:
        if host(url) not in allowed or BAD.search(url): continue
        checked.add(url)
        row={'source':url,'status':'unverified','competitor_links':'','saveitbro_links':'','rel':'','editorial_hint':'','new_candidate':url not in history and url not in seeds}
        try:
            p,base=fetch(url,allowed)
            links=[(urljoin(base,h),rel,t) for h,rel,t in p.links]
            own={(h,rel) for h,rel,t in links if match(h,'saveitbro.com') and urlsplit(h).scheme in ('https','http')}
            rivals={h for h,rel,t in links if any(match(h,d) for d in RIVALS)}
            row.update(status='checked',competitor_links=len(rivals),saveitbro_links=len({h for h,rel in own}),rel=';'.join(sorted({rel or 'unspecified' for h,rel in own})),editorial_hint='; '.join(dict.fromkeys(h for h,rel,t in links if host(h)==host(base) and re.search(r'write.for.us|guest.post|editorial|submit.a.tool',h+' '+t,re.I)))[:500])
            for h,rel,t in links:
                n=norm(h)
                if n and host(n) in allowed and not BAD.search(n) and TOPIC.search((n+' '+t).replace('-',' ')) and n not in queue and n not in history:
                    found[n]=host(n)
        except Exception as e: row['status']='unverified: '+str(e)[:120]
        rows.append(row)
        history[url]={'last_checked':datetime.now(timezone.utc).isoformat(),'status':row['status'],'saveitbro_links':row['saveitbro_links']}
    # Rotate bounded candidates; preserve previously discovered URLs.
    new=list(found)[:5]
    for url in new: history[url]={'status':'candidate; not yet checked'}
    state.write_text(json.dumps(history,indent=2))
    with open('report.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['source','status','competitor_links','saveitbro_links','rel','editorial_hint','new_candidate']); w.writeheader(); w.writerows(rows)
    with open('opportunities.csv','w',newline='') as f:
        w=csv.writer(f); w.writerow(['url','publisher','status']); w.writerows((u,found[u],'candidate; editorial eligibility and cost unverified') for u in new)
    print(f'Checked {len(rows)} pages; discovered {len(new)} candidates. No submissions made.')
if __name__=='__main__': main()
