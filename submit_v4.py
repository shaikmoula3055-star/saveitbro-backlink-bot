"""One explicitly authorized directory; no paid extras or repeated submissions."""
import os,json,urllib.request,urllib.parse,uuid
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
    try:
        check=request(BASE+'/check?'+urllib.parse.urlencode({'url':SITE}))
        if check.get('available') is False: status['status']='already listed or pending; no duplicate submission'
        elif check.get('available') is not True: status['status']='availability unconfirmed; stopped'
        elif os.getenv('ALLOW_SUBMIT')!='true': status['status']='manual submission not enabled'
        elif not os.getenv('CONTACT_EMAIL'): status['status']='missing private contact email secret'
        else:
            result=request(BASE,{'websiteUrl':SITE,'name':'SaveItBro','summary':'SaveItBro helps users download Instagram media they own or have permission to save using a browser.','category':'social-publishing','tags':['free','web'],'pricingLabel':'Free','contactEmail':os.environ['CONTACT_EMAIL'],'extras':[],'extrasConfirmedWithUser':True,'requestKey':str(uuid.uuid5(uuid.NAMESPACE_URL,'queststack:'+SITE))})
            listing=result.get('listing',{})
            status['status']='submission response received; '+str(listing.get('status','review status unknown'))
        # Never write raw responses or tokens to public artifacts.
    except Exception as e: status['status']='stopped: '+type(e).__name__
    Path('submission-result.json').write_text(json.dumps(status,indent=2))
    print(status['status'])
if __name__=='__main__': main()
