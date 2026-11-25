"""V3: free GDELT discovery plus bounded, read-only publisher audits."""
import xml.etree.ElementTree as ET
import csv, json, re, time, socket, ipaddress, urllib.request, urllib.error
from urllib.parse import urlsplit, urljoin, urlencode, urlunsplit
from urllib.robotparser import RobotFileParser
from pathlib import Path
from datetime import datetime, timezone
from bot_v2 import Page, TOPIC, BAD, host, match, RIVALS, norm

UA='SaveItBroLinkAudit/3.1'
HINT=re.compile(r'write.for.us|guest.post|submit.a.tool|submit.your|editorial.guidelines|contribute',re.I)
EXCLUDE=re.compile(r'facebook\.com|instagram\.com|youtube\.com|reddit\.com|tiktok\.com|pinterest\.com|link.farm|buy.backlinks|casino|betting|porn',re.I)
def safe(url):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError('unsafe URL')
    if not all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)):
        raise ValueError('nonpublic address')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
opener=urllib.request.build_opener(NoRedirect())
def get(url,limit=2000000):
    safe(url)
    with opener.open(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=10) as f:
        return f.read(limit),f.headers.get('Content-Type','')
robots={}
def check_robots(url):
    origin='https://'+urlsplit(url).netloc
    if origin not in robots:
        rp=RobotFileParser()
        try: rp.parse(get(origin+'/robots.txt',200000)[0].decode('utf8','replace').splitlines())
        except urllib.error.HTTPError as e:
            if e.code==404: rp.parse([])
            else: raise
        robots[origin]=rp
    rp=robots[origin]
    if not rp.can_fetch(UA,url): raise ValueError('robots denied')
    delay=max(2,rp.crawl_delay(UA) or 0)
    if delay>10: raise ValueError('crawl delay exceeds budget')
    time.sleep(delay)
def fetch(url):
    for _ in range(6):
        if not eligible(url): raise ValueError('excluded destination')
        check_robots(url)
        try:
            raw,typ=get(url)
            if 'html' not in typ: raise ValueError('not HTML')
            p=Page(); p.feed(raw.decode('utf8','replace')); p.final_url=url
            return p
        except urllib.error.HTTPError as e:
            if e.code not in (301,302,303,307,308) or not e.headers.get('Location'): raise
            url=urljoin(url,e.headers['Location'])
            safe(url)
    raise ValueError('redirect limit')
def eligible(u):
    return bool(u and not BAD.search(u) and not EXCLUDE.search(u) and not any(match(u,d) for d in (*RIVALS,'saveitbro.com','inflact.com','toolzu.com','smallseotools.com','igram.world','savefrom.net','snapinsta.to','sssinstagram.com','instasupersave.com')))
def gdelt():
    query='("Instagram downloader" OR "download Instagram videos" OR "save Instagram reels") sourcelang:english'
    url='https://api.gdeltproject.org/api/v2/doc/doc?'+urlencode({'query':query,'mode':'artlist','format':'json','maxrecords':50,'timespan':'3months'})
    try:
        data=json.loads(get(url)[0])
        return [(norm(a.get('url','')),a.get('title',''),a.get('sourcecountry','')) for a in data.get('articles',[])], 'GDELT response received'
    except urllib.error.HTTPError as e:
        if e.code==429: return [],'GDELT rate limited; deferred until next daily run'
        return [],'GDELT HTTP '+str(e.code)
    except Exception as e: return [],'GDELT unavailable: '+str(e)[:150]

def discover():
    rows,status=gdelt()
    # Public WordPress publisher search API, no credentials required.
    for domain in ('www.leptidigital.fr','socialbu.com','viralmango.com'):
        try:
            url='https://'+domain+'/wp-json/wp/v2/search?'+urlencode({'search':'instagram downloader','per_page':10})
            check_robots(url)
            data=json.loads(get(url)[0])
            rows.extend((norm(a.get('url','')),a.get('title',''),'') for a in data if isinstance(a,dict))
            status+='; '+domain+' search responded'
        except Exception as e: status+='; '+domain+' search unavailable: '+str(e)[:80]
    return rows,status
def main():
    state=Path('state.json')
    history=json.loads(state.read_text()) if state.exists() else {}
    seeds=list(dict.fromkeys(filter(None,(norm(x.strip()) for x in Path('candidates.txt').read_text().splitlines()))))
    old_domains={host(u) for u in history}|{host(u) for u in seeds}
    results, discovery_status=discover()
    results.sort(key=lambda a:a[2] not in ('United States','United Kingdom','Australia'))
    candidates={}
    def add(u,title,country,source):
        if eligible(u) and u not in history and u not in seeds and TOPIC.search((u+' '+title).replace('-',' ')):
            candidates.setdefault(u,{'source':source,'country':country,'title':title})
    for u,t,c in results: add(u,t,c,'GDELT')
    def priority(u): return (not bool(history[u].get('saveitbro_links')),history[u].get('last_checked',''))
    queue=list(dict.fromkeys(seeds+sorted(history,key=priority)[:8]))
    rows=[]; verified=[]
    def audit(u,meta=None):
        prev=history.get(u,{})
        row={'source':u,'status':'unverified','competitor_links':'','saveitbro_links':'','rel':'','editorial_hint':'','change':'','country':(meta or prev).get('country','')}
        try:
            p=fetch(u)
            links=[(urljoin(p.final_url,h),rel,t) for h,rel,t in p.links]
            own={(h,rel) for h,rel,t in links if match(h,'saveitbro.com') and urlsplit(h).scheme in ('http','https')}
            rivals={h for h,rel,t in links if any(match(h,d) for d in RIVALS)}
            hints=list(dict.fromkeys(h for h,rel,t in links if host(h)==host(p.final_url) and HINT.search(h+' '+t)))
            row['source']=p.final_url
            row.update(status='checked',competitor_links=len(rivals),saveitbro_links=len({h for h,rel in own}),rel=';'.join(sorted({rel or 'unspecified' for h,rel in own})),editorial_hint='; '.join(hints)[:800])
            if prev.get('saveitbro_links') and not own: row['change']='previous link not observed'
            elif own and not prev.get('saveitbro_links'): row['change']='newly observed'
            for h,rel in own: verified.append([p.final_url,h,rel or 'unspecified'])
            for h,rel,t in links: add(norm(h),t,'','publisher link')
            history[u]={**prev,**(meta or {}),'last_checked':datetime.now(timezone.utc).isoformat(),'status':'checked','saveitbro_links':row['saveitbro_links']}
        except Exception as e:
            row['status']='unverified: '+str(e)[:120]
            history[u]={**prev,**(meta or {}),'last_checked':datetime.now(timezone.utc).isoformat(),'status':row['status']}
        rows.append(row)
        return row
    for u in queue:
        if eligible(u): audit(u)
    opportunities=[]; used=set()
    for u,m in sorted(candidates.items(),key=lambda item:(host(item[0]) in old_domains,item[1]['country'] not in ('United States','United Kingdom','Australia'))):
        if len(rows)>=24: break
        if host(u) in used: continue
        used.add(host(u))
        row=audit(u,m)
        if row['status']!='checked': continue
        if not row['editorial_hint'] and not row['competitor_links']: continue
        if len(rows)>=24: break
        opportunities.append([row['source'],host(row['source']),m['source'],m['country'],host(u) not in old_domains,row['status'],row['editorial_hint'],'free eligibility and acceptance require manual review'])
        if len(opportunities)>=5: break
    state.write_text(json.dumps(history,indent=2))
    with open('report.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['source','status','competitor_links','saveitbro_links','rel','editorial_hint','change','country']); w.writeheader(); w.writerows(rows)
    for name,header,data in [('opportunities.csv',['url','domain','discovery_source','country','new_domain','check_status','editorial_hint','eligibility'],opportunities),('verified-links.csv',['source','target','rel'],verified)]:
        with open(name,'w',newline='') as f:
            w=csv.writer(f); w.writerow(header); w.writerows(data)
    Path('discovery-status.txt').write_text(discovery_status+'\nNo submissions made. Country is publisher metadata, not audience location.\n')
    print(discovery_status, 'Candidates:',len(opportunities),'Observed links:',len(verified))
if __name__=='__main__': main()
