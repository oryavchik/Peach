"""Use gcloud's short-lived login token without saving or printing credentials.

No billing activation/linking or Cloud Run/SQL/Dataflow calls are implemented.
"""
import json
import os
from pathlib import Path
import subprocess
import ssl
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
PROJECT='peach-510910'
OUT=ROOT/'docs/lab9-evidence'
GCLOUD=ROOT/'.local/lab9-tools/google-cloud-sdk/bin/gcloud'


def call(url,method='GET',body=None):
    env={**os.environ,'CLOUDSDK_PYTHON':'/Library/Frameworks/Python.framework/Versions/3.13/bin/python3'}
    token=subprocess.check_output([str(GCLOUD),'auth','print-access-token'],env=env,text=True).strip()
    assert url.startswith(('https://firebase.googleapis.com/','https://firebasehosting.googleapis.com/','https://firestore.googleapis.com/','https://cloudbilling.googleapis.com/'))
    data=None if body is None else json.dumps(body).encode()
    request=Request(url,data=data,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','x-goog-user-project':PROJECT})
    try:
        with urlopen(request,timeout=60,context=ssl.create_default_context(cafile="/etc/ssl/cert.pem")) as r:return json.load(r)
    except HTTPError as e:
        response=json.loads(e.read());return {'request_failed':True,'http_status':e.code,'response':response}


def main():
    billing=json.loads(subprocess.check_output([str(GCLOUD),'billing','projects','describe',PROJECT,'--format=json'],env={**os.environ,'CLOUDSDK_PYTHON':'/Library/Frameworks/Python.framework/Versions/3.13/bin/python3'},text=True))
    assert not billing.get('request_failed') and billing['billingEnabled'] is False,billing
    (OUT/'billing-disabled.json').write_text(json.dumps(billing,indent=2)+'\n')
    firebase=call(f'https://firebase.googleapis.com/v1beta1/projects/{PROJECT}')
    if firebase.get('http_status')==404:
        firebase=call(f'https://firebase.googleapis.com/v1beta1/projects/{PROJECT}:addFirebase','POST',{})
        if 'name' in firebase and firebase['name'].startswith('operations/'):
            operation=firebase['name']
            for _ in range(30):
                firebase=call('https://firebase.googleapis.com/v1beta1/'+operation)
                if firebase.get('done'):break
                time.sleep(2)
    (OUT/'firebase-project.json').write_text(json.dumps(firebase,indent=2)+'\n')
    print(json.dumps({'firebase':firebase},indent=2))

if __name__=='__main__':main()
