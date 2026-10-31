import base64
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('lab8_cloud_alert',Path(__file__).parents[1]/'cloud/alert.py')
alert=importlib.util.module_from_spec(spec);spec.loader.exec_module(alert)


def record(status, invoice):
    data=json.dumps({'invoiceId':invoice,'status':status,'paymentMethod':'card'}).encode()
    return {'kinesis':{'data':base64.b64encode(data).decode()}}


class CloudAlertTests(unittest.TestCase):
    def test_duplicates_and_early_invocation_do_not_publish(self):
        r=record('failure','one')
        out=alert.handler({'Records':[r,r,record('created','two')]},None)
        self.assertEqual(out['state']['methods']['card'],{'terminal':1,'failure':1})
        out2=alert.handler({'Records':[r],'state':out['state']},None)
        self.assertEqual(out2['state']['methods']['card']['terminal'],1)
    def test_final_window_threshold_and_no_network(self):
        calls=[]
        sns=types.SimpleNamespace(publish=lambda **kw:calls.append(kw))
        module=types.SimpleNamespace(client=lambda name:sns)
        with patch.dict(sys.modules,{'boto3':module}),patch.dict('os.environ',{'ALERT_TOPIC_ARN':'test-only'}):
            alert.handler({'Records':[record('failure','1'),record('success','2')],
                           'isFinalInvokeForWindow':True,'window':{},'shardId':'one'},None)
        self.assertEqual(len(calls),1)
        self.assertEqual(json.loads(calls[0]['Message'])['failure_rate'],.5)


if __name__=='__main__':unittest.main()
