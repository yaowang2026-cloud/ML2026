import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.app import create_app
from backend.test_workflow import fields

class AutoSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.app=create_app(self.temp.name); self.client=self.app.test_client()
    def seed(self, unresolved=False, confirmed=True):
        record=dict(record_id='test',revision=0,page_count=1,fields=fields())
        for field in record['fields']: field['resolved']=True
        record['fields'][0].update(value='PAT-1',status='KNOWN',user_confirmed=confirmed)
        if unresolved: record['fields'][-1]['resolved']=False
        with sqlite3.connect(Path(self.temp.name)/'sessions.sqlite3') as db:
            db.execute('INSERT INTO sessions VALUES (?,?,0)',('test',json.dumps(record)))
        db.close()
    def test_last_manual_edit_moves_and_exports(self):
        self.seed(unresolved=True)
        result=self.client.post('/api/records/test/manual',json={'revision':0,'changes':{'referral to higher care':'0'}})
        self.assertEqual(result.status_code,200); self.assertTrue(result.json['saved'])
        self.assertEqual(self.client.get('/api/dataset?status=draft').json['total'],0)
        self.assertEqual(self.client.get('/api/dataset?status=saved').json['total'],1)
        with (Path(self.temp.name)/'registry.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(rows[0]['id'],'PAT-1'); self.assertEqual(rows[0]['referral to higher care'],'0')
    def test_last_review_blank_can_complete(self):
        self.seed(unresolved=True)
        result=self.client.post('/api/records/test/review',json={'revision':0,'field':'referral to higher care','action':'missing'})
        self.assertTrue(result.json['saved'])
    def test_reconcile_existing_and_no_duplicates(self):
        self.seed()
        for _ in range(2): create_app(self.temp.name)
        self.assertTrue(self.client.get('/api/records/test').json['saved'])
        self.assertEqual(self.client.get('/api/dataset?status=saved').json['total'],1)
    def test_unconfirmed_patient_stays_pending(self):
        self.seed(confirmed=False); create_app(self.temp.name)
        self.assertFalse(self.client.get('/api/records/test').json['saved'])
    def test_csv_failure_rolls_back_edit_and_status(self):
        self.seed(unresolved=True)
        with patch('backend.app.os.replace',side_effect=PermissionError('locked')):
            result=self.client.post('/api/records/test/manual',json={'revision':0,'changes':{'referral to higher care':'0'}})
        self.assertEqual(result.status_code,503)
        record=self.client.get('/api/records/test').json
        self.assertFalse(record['saved']); self.assertEqual(record['revision'],0)

if __name__ == '__main__': unittest.main()
