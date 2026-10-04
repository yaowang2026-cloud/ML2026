import sys
import tempfile
import unittest
import io
import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
from backend import extraction as engine

def fields():
    return [dict(name=name, label=name, value=None, status='NOT_PROVIDED', evidence=None, reason=None, question=None, resolved=False) for name in engine.TARGET_COLUMNS]

def photo():
    stream = io.BytesIO()
    Image.new('RGB', (10,10), 'white').save(stream, format='PNG')
    stream.seek(0)
    return stream

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(self.temp.name)
        self.client = self.app.test_client()
    def tearDown(self): self.temp.cleanup()
    def upload(self, count=3):
        with patch.object(engine, 'extract_images', return_value=fields()) as model:
            response = self.client.post('/api/extract', data={'images': [(photo(), f'{i}.png') for i in range(count)]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(model.call_args.args[0]), count)
        return response.json
    def test_many_images_and_persistence(self):
        result = self.upload(12)
        self.assertEqual(result['page_count'], 12)
        self.assertEqual(len(result['missing']), 31)
        other = create_app(self.temp.name).test_client()
        self.assertEqual(other.get('/api/records/' + result['record_id']).json['fields'], result['fields'])
    def test_invalid_upload_and_private_paths(self):
        self.assertEqual(self.client.post('/api/extract').status_code, 400)
        self.assertEqual(self.client.post('/api/extract', data={'images': (io.BytesIO(b'fake'), 'a.png')}).status_code, 400)
        self.assertEqual(self.client.get('/work/registry/sessions.sqlite3').status_code, 404)
        with self.client.get('/app.js') as response: self.assertEqual(response.status_code, 200)
    def test_review_save_retry_and_csv(self):
        result = self.upload()
        base = '/api/records/' + result['record_id']
        self.assertEqual(self.client.post(base + '/finalize', json={'confirm': True, 'revision': 0}).status_code, 422)
        reply = SimpleNamespace(message=SimpleNamespace(content='{"value": 28, "clear": true, "message": "Age: 28"}'))
        with patch.object(engine.pipeline, 'chat', return_value=reply) as llm:
            response = self.client.post(base + '/review', json={'revision': 0, 'field': 'age (years)', 'action': 'modify', 'response': '28 ans'})
            self.assertEqual(response.status_code, 200)
            llm.assert_called_once()
        result = response.json
        self.assertFalse(result['ready_to_save'])
        self.assertEqual(result['review'][0]['value'], 28)
        self.assertEqual(self.client.post(base + '/review', json={'revision': 0, 'field': 'age (years)', 'action': 'confirm'}).status_code, 409)
        for f in result['fields']:
            response = self.client.post(base + '/review', json={'revision': result['revision'], 'field': f['name'], 'action': 'confirm' if f['name'] == 'age (years)' else 'missing'})
            self.assertEqual(response.status_code, 200)
            result = response.json
        self.assertTrue(result['ready_to_save'])
        for _ in range(2):
            self.assertEqual(self.client.post(base + '/finalize', json={'revision': result['revision'], 'confirm': True}).status_code, 200)
        with (Path(self.temp.name)/'registry.csv').open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f); rows = list(reader)
            self.assertEqual(reader.fieldnames, engine.TARGET_COLUMNS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['age (years)'], '28')
        self.assertEqual(rows[0]['id'], '')
        self.assertEqual(self.client.post(base + '/review', json={'revision': result['revision'], 'field': 'id', 'action': 'missing'}).status_code, 409)
    def test_invalid_correction_and_null_confirmation(self):
        field = fields()[1]
        with self.assertRaises(ValueError): engine.apply_review(field, 'confirm')
        reply = SimpleNamespace(message=SimpleNamespace(content='{"value": "unknown", "clear": false, "message": "Ambiguous"}'))
        with patch.object(engine.pipeline, 'chat', return_value=reply), self.assertRaises(ValueError): engine.apply_review(field, 'modify', 'maybe')
        self.assertIsNone(field['value'])
    def test_ocr_routing_and_page_order(self):
        raw = fields()
        items = []
        for f in raw:
            items.append({'field_name': f['name'], 'value': None, 'status':'NOT_PROVIDED','evidence':None})
        items[0].update(value='201',status='KNOWN',evidence='pt 201')
        items[1].update(value=28,status='KNOWN',evidence='invented evidence')
        items[2].update(value=5,status='KNOWN',evidence='pt 201')
        extraction = engine.pipeline.ExtractionResponse.model_validate({'fields':items})
        with patch.object(engine.pipeline, 'images_to_ocr_text', side_effect=['pt 201', 'other page']) as ocr, patch.object(engine.pipeline, 'extract_with_ollama', return_value=extraction) as extract:
            result = engine.extract_images(['a.png','b.png'])
            self.assertEqual(ocr.call_count, 2)
            self.assertIn('--- Page 2 ---', extract.call_args.args[0])
        self.assertTrue(result[0]['resolved'])
        self.assertEqual(result[1]['status'], 'NEEDS_REVIEW')
        self.assertEqual(result[2]['status'], 'NEEDS_REVIEW')
    def test_live_progress_events(self):
        from uuid import uuid4
        progress_id = str(uuid4())
        def model(paths, progress):
            progress('Lecture page 1/1')
            snapshot = self.client.get('/api/progress/' + progress_id).json
            self.assertIn('Lecture page 1/1', snapshot['events'])
            progress('Extraction des champs')
            return fields()
        with patch.object(engine, 'extract_images', side_effect=model):
            result = self.client.post('/api/extract', data={'images': (photo(), 'test.png'), 'progress_id': progress_id})
        self.assertEqual(result.status_code, 200)
        events = self.client.get('/api/progress/' + progress_id).json['events']
        self.assertIn('Préparation', events[0])
        self.assertIn('terminée', events[-1])
        self.assertEqual(events[1:3], ['Lecture page 1/1', 'Extraction des champs'])
        duplicate = self.client.post('/api/extract', data={'images': (photo(), 'test.png'), 'progress_id': progress_id})
        self.assertEqual(duplicate.status_code, 409)

    def test_zero_and_formula(self):
        self.assertTrue(engine.valid_value('hiv test result', 0))
        self.assertFalse(engine.valid_value('hiv test result', True))
        self.assertFalse(engine.valid_value('age (years)', float('nan')))
        self.assertEqual(engine.csv_value('=SUM(1)'), "'=SUM(1)")

if __name__ == '__main__': unittest.main()
