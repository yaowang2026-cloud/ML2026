import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import model_provider as provider, pipeline
from backend.test_workflow import WorkflowTests, fields, photo

class ProviderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        setting = patch.object(provider, 'CONFIG_FILE', Path(temporary.name) / 'absent.ini')
        setting.start()
        self.addCleanup(setting.stop)

    def test_local_exact_passthrough_and_reset(self):
        from unittest.mock import Mock
        local = Mock(return_value='local')
        arguments = dict(model=pipeline.MODEL, messages=[{'role':'system','content':'unchanged'}], options=pipeline.OCR_OPTIONS, think=False)
        self.assertEqual(provider.dispatch(local, **arguments), 'local')
        local.assert_called_once_with(**arguments)
        with self.assertRaises(RuntimeError):
            with provider.use_provider('openai'):
                raise RuntimeError()
        self.assertEqual(provider._selection.get(), ('local', None))

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test-key'})
    def test_image_schema_and_settings(self):
        result = {'status':'completed','output':[{'content':[{'type':'output_text','text':'test'}]}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'page.png'; path.write_bytes(b'image')
            schema=pipeline.ExtractionResponse.model_json_schema()
            original=json.dumps(schema)
            with patch.object(provider, 'urlopen', return_value=io.BytesIO(json.dumps(result).encode())) as network:
                with provider.use_provider('openai','gpt-4.1-mini'):
                    reply=provider.dispatch(None, messages=[{'role':'system','content':pipeline.OCR_SYSTEM_PROMPT},{'role':'user','content':'unchanged','images':[str(path)]}], options=pipeline.OCR_OPTIONS, format=schema)
            body=json.loads(network.call_args.args[0].data)
            self.assertEqual(body['input'][0]['content'][0]['text'],pipeline.OCR_SYSTEM_PROMPT)
            self.assertEqual(body['max_output_tokens'],8192)
            self.assertEqual(body['temperature'],0)
            self.assertFalse(body['store'])
            self.assertTrue(body['input'][1]['content'][1]['image_url'].startswith('data:image/png;base64,'))
            strict=body['text']['format']['schema']['$defs']['ExtractedField']
            self.assertFalse(strict['additionalProperties'])
            self.assertEqual(set(strict['required']),set(strict['properties']))
            self.assertEqual(original,json.dumps(schema))
            self.assertEqual(reply.message.content,'test')

    def test_missing_key_no_network(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':''}), patch.object(provider,'urlopen') as network:
            with provider.use_provider('openai'), self.assertRaises(provider.ProviderError):
                provider.dispatch(None, messages=[])
            network.assert_not_called()

    @patch.dict(os.environ, {'OPENAI_API_KEY':'test-key'})
    def test_incomplete_and_refusal(self):
        for result in [{'status':'incomplete'}, {'status':'completed','output':[{'content':[{'type':'refusal'}]}]}]:
            with patch.object(provider,'urlopen',return_value=io.BytesIO(json.dumps(result).encode())):
                with provider.use_provider('openai'), self.assertRaises(provider.ProviderError):
                    provider.dispatch(None,messages=[])

class ProviderWorkflowTests(WorkflowTests):
    def setUp(self):
        super().setUp()
        setting = patch.object(provider, 'CONFIG_FILE', Path(self.temp.name) / 'absent.ini')
        setting.start()
        self.addCleanup(setting.stop)

    def test_provider_persisted_for_corrections(self):
        seen=[]
        def extract(*args,**kwargs):
            seen.append(provider._selection.get());return fields()
        with patch.dict(os.environ, {'OPENAI_MODEL':'gpt-4.1-mini'}), patch('backend.extraction.extract_images',side_effect=extract):
            response=self.client.post('/api/extract',data={'provider':'openai','images':(photo(),'test.png')})
        self.assertEqual(response.status_code,200)
        record=response.json
        self.assertEqual(record['model_provider'],'openai')
        self.assertEqual(seen,[('openai','gpt-4.1-mini')])
        with patch('backend.extraction.apply_review',side_effect=lambda *args: seen.append(provider._selection.get())):
            response=self.client.post('/api/records/'+record['record_id']+'/review',json={'revision':0,'field':'id','action':'modify','response':'123'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(seen[-1],('openai','gpt-4.1-mini'))
        self.assertEqual(provider._selection.get(),('local',None))
        self.assertEqual(self.client.post('/api/extract',data={'provider':'unknown'}).status_code,400)

if __name__ == '__main__': unittest.main()
