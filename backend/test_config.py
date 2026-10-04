import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import model_provider as provider
from backend.app import create_app

class ConfigTests(unittest.TestCase):
    def test_file_priority_reload_and_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.ini'
            with patch.object(provider,'CONFIG_FILE',path), patch.dict(os.environ,{'OPENAI_API_KEY':'env-key','OPENAI_MODEL':'env-model'}):
                self.assertEqual(provider.online_model(),'env-model')
                path.write_text('[openai]\napi_key = file-key\nmodel = file-model\n',encoding='utf-8-sig')
                self.assertEqual(provider.online_model(),'file-model')
                self.assertEqual(provider.online_setting('api_key','OPENAI_API_KEY'),'file-key')
                path.write_text('[openai]\napi_key =\nmodel = changed-model\n',encoding='utf-8')
                self.assertEqual(provider.online_model(),'changed-model')
                self.assertEqual(provider.online_setting('api_key','OPENAI_API_KEY'),'env-key')
                path.write_text('invalid secret contents',encoding='utf-8')
                with self.assertRaises(provider.ProviderError) as error: provider.online_model()
                self.assertNotIn('secret',str(error.exception))
                with provider.use_provider('local'):
                    self.assertEqual(provider.dispatch(lambda **kw:'local'), 'local')
    def test_private_file_not_served(self):
        with tempfile.TemporaryDirectory() as folder:
            client=create_app(folder).test_client()
            self.assertEqual(client.get('/backend/openai-config.ini').status_code,404)
            self.assertEqual(client.get('/openai-config.ini').status_code,404)
if __name__ == '__main__': unittest.main()
