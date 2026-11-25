"""One explicitly authorized directory; no paid extras or repeated submissions."""
import os,json,urllib.request,urllib.parse,urllib.error,uuid
from pathlib import Path
from bot_v33 import fetch,match
BASE='https://queststack.io/api/v1/listings'
SITE='https://saveitbro.com'
def request(url,payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json','User-Agent':'SaveItBroSubmission/4.0'})
    from bot_v33 import opener
    with opener.open(req,timeout=20) as f: return json.load(f)
def main():
    status={'directory':'QuestStack','status':'not submitted'}
    stage='availability check'
    try:
        check=request(BASE+'/check?'+urllib.parse.urlencode({'url':SITE}))
        if check.get('available') is False: status['status']='already listed or pending; no duplicate submission'
        elif check.get('available') is not True: status['status']='availability unconfirmed; stopped'
        elif os.getenv('ALLOW_SUBMIT')!='true': status['status']='manual submission not enabled'
        elif not os.getenv('CONTACT_EMAIL'): status['status']='missing private contact email secret'
        else:
            stage='submission POST'
            result=request(BASE,{'websiteUrl':SITE,'name':'SaveItBro','summary':'SaveItBro helps users download Instagram media they own or have permission to save using a browser.','category':'social-publishing','tags':['free','web'],'pricingLabel':'Free','contactEmail':os.environ['CONTACT_EMAIL'],'extras':[],'extrasConfirmedWithUser':True,'requestKey':str(uuid.uuid5(uuid.NAMESPACE_URL,'queststack:'+SITE))})
            listing=result.get('listing',{})
            status['status']='submission response received; '+str(listing.get('status','review status unknown'))
        # Never write raw responses or tokens to public artifacts.
    except urllib.error.HTTPError as e:
        status.update(status='HTTP error; no automatic retry',stage=stage,http_code=e.code)
        retry=e.headers.get('Retry-After','')
        if retry.isdigit(): status['retry_after_seconds']=int(retry)
        # Never expose server echoes, emails or management tokens in public artifacts.
        try:
            body=json.loads(e.read(8192))
            status['response_type']='JSON'
            allowed={'invalid_request','validation_error','rate_limited','duplicate','already_exists','forbidden','unauthorized','not_found','invalid_payload','conflict'}
            for k in ('code','error'):
                if isinstance(body.get(k),str) and body[k] in allowed: status[k]=body[k]
        except Exception: status['response_type']='non-JSON or unreadable'
        if e.code==429: status['guidance']='Rate limited; wait before manual review.'
        elif e.code==409: status['guidance']='Possible existing listing; verify before retry.'
        elif e.code in (400,422): status['guidance']='Request rejected; review official requirements.'
        elif e.code in (401,403): status['guidance']='Access denied; do not bypass.'
        elif e.code==402: status['guidance']='Payment requested; stopped.'
        elif e.code>=500: status['guidance']='Server error; outcome unknown; check availability before any retry.'
    except Exception as e: status.update(status='stopped: '+type(e).__name__,stage=stage)
    Path('submission-result.json').write_text(json.dumps(status,indent=2))
    print(status['status'])
if __name__=='__main__': main()
