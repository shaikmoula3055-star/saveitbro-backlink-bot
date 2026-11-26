import json, csv, os, hashlib, urllib.request, urllib.error, re
from pathlib import Path
from datetime import datetime, timezone
from bot_v33 import fetch, get, eligible, norm, host, match, main as audit
from urllib.parse import urljoin, quote
def save(p,d): Path(p).write_text(json.dumps(d,indent=2,sort_keys=True))
def load(p): return json.loads(Path(p).read_text()) if Path(p).exists() else {}
def main():
    ledger=load('v5-ledger.json')
    candidates=ledger.setdefault('candidates',{})
    published=ledger.setdefault('publications',{})
    observed=ledger.setdefault('observed_links',{})
    # Curated starting points; not presumed eligible.
    sources=['https://alternativeto.net/','https://www.launchingnext.com/','https://startupstash.com/','https://www.indiehackers.com/']
    try:
        raw,_=get('https://raw.githubusercontent.com/maxlibin/free-directory-submissions/main/README.md',500000)
        for u in re.findall(r'https://[^\s<>)\]"]+',raw.decode('utf8','replace')):
            if re.search(r'directory|startup|webapp|submit|launch|software',u,re.I) and not re.search(r'github|\bai\b|\.ai/|queststack',u,re.I):
                sources.append(u.rstrip('.,'))
    except Exception: pass
    queue=[]
    for u in sources:
        try:
            u=norm(u)
            if eligible(u) and host(u) not in {host(x) for x in candidates} and host(u) not in {host(x) for x in queue}: queue.append(u)
        except Exception: pass
    for u in queue[:5]:
        entry={'status':'manual eligibility review required'}
        try:
            p=fetch(u)
            entry['url']=p.final_url
            entry['policy_links']=[urljoin(p.final_url,h) for h,rel,t in p.links if host(urljoin(p.final_url,h))==host(p.final_url) and re.search(r'submit|guidelines|add a|contribute',h+' '+t,re.I)][:5]
        except Exception as e: entry['status']='unverified: '+type(e).__name__
        candidates[u]=entry
    save('v5-ledger.json',ledger)
    audit()
    with open('verified-links.csv') as f:
        for row in csv.DictReader(f):
            observed[row['source']+' | '+row['target']]={**row,'last_verified':datetime.now(timezone.utc).isoformat()}
    # Only explicitly reviewed original articles; never generate repetitive automated posts.
    for path in sorted(Path('approved-posts').glob('*.json'))[:20]:
        post=json.loads(path.read_text())
        key=hashlib.sha256((post['title']+'\n'+post['content']).encode()).hexdigest()
        platform=post.get('platform')
        if key in published or post.get('approved') is not True: continue
        if platform=='blogger':
            token=os.getenv('BLOGGER_TOKEN'); site=os.getenv('BLOGGER_BLOG_ID')
            if not token or not site or not site.isdigit(): continue
            endpoint='https://www.googleapis.com/blogger/v3/blogs/'+site+'/posts'
            payload={'title':post['title'],'content':post['content']}
        elif platform=='wordpress':
            token=os.getenv('WORDPRESS_TOKEN'); site=os.getenv('WORDPRESS_SITE_ID')
            if not token or not site or not site.isdigit(): continue
            endpoint='https://public-api.wordpress.com/rest/v1.1/sites/'+site+'/posts/new'
            payload={'title':post['title'],'content':post['content'],'status':'publish'}
        else: continue
        # Reserve durably in git before POST; ambiguous failures are never retried.
        published[key]={'platform':platform,'status':'reserved; outcome unknown'}
        save('v5-ledger.json',ledger)
        import subprocess
        subprocess.run(['git','add','v5-ledger.json'],check=True)
        subprocess.run(['git','commit','-m','Reserve approved publication'],check=True)
        subprocess.run(['git','push'],check=True)
        try:
            req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            from bot_v33 import opener
            with opener.open(req,timeout=20) as response: result=json.load(response)
            published[key].update(status='response received; public verification pending',url=result.get('url') or result.get('URL') or '')
        except urllib.error.HTTPError as e: published[key].update(status='stopped; no retry',http_code=e.code)
        except Exception: published[key].update(status='outcome unknown; no retry')
        break
    for record in published.values():
        if not record.get('url'): continue
        try:
            p=fetch(record['url'])
            links=[urljoin(p.final_url,h) for h,rel,t in p.links if match(urljoin(p.final_url,h),'saveitbro.com')]
            record['status']='public backlink verified' if links else 'public page checked; backlink absent'
            for link in links: observed[p.final_url+' | '+link]={'source':p.final_url,'target':link,'last_verified':datetime.now(timezone.utc).isoformat()}
        except Exception: record['status']='public verification unavailable'
    save('v5-ledger.json',ledger)
    save('v5-report.json',{'new_candidates':[{'candidate':u,**candidates[u]} for u in queue[:5]],'publications':published,'historically_observed_links':len(observed),'queststack':'disabled','note':'Candidates are not confirmed free or eligible; historical links are not necessarily live today.'})
if __name__=='__main__': main()
