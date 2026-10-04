"""Request-scoped provider adapter; the notebook prompts/options remain unchanged."""
import base64
import copy
import configparser
import json
import mimetypes
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_selection = ContextVar('model_selection', default=('local', None))
CONFIG_FILE = Path(__file__).resolve().parent / 'openai-config.ini'


class ProviderError(RuntimeError):
    pass


def online_setting(name, environment, default=''):
    # Reload on use so private file edits do not require a server restart.
    config = configparser.ConfigParser(interpolation=None)
    try:
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open(encoding='utf-8-sig') as source:
                config.read_file(source)
        value = config.get('openai', name, fallback='').strip()
    except (OSError, UnicodeError, configparser.Error):
        raise ProviderError('Cannot read backend/openai-config.ini. Check its INI format and permissions.') from None
    return value or os.getenv(environment, default).strip()


def online_model():
    return online_setting('model', 'OPENAI_MODEL', 'gpt-4.1-mini')


@contextmanager
def use_provider(provider='local', model=None):
    if provider not in {'local', 'openai'}:
        raise ValueError('Unknown model provider.')
    token = _selection.set((provider, model or (online_model() if provider == 'openai' else None)))
    try:
        yield
    finally:
        _selection.reset(token)


def strict_schema(schema):
    schema = copy.deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            node.pop('default', None)
            if node.get('type') == 'object':
                node['additionalProperties'] = False
                node['required'] = list(node.get('properties', {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(schema)
    return schema


def dispatch(local_chat, **kwargs):
    provider, model = _selection.get()
    if provider == 'local':
        return local_chat(**kwargs)
    key = online_setting('api_key', 'OPENAI_API_KEY')
    if not key:
        raise ProviderError('OpenAI: enter api_key in backend/openai-config.ini, or set OPENAI_API_KEY on the backend.')
    messages = []
    for original in kwargs['messages']:
        content = [{'type': 'input_text', 'text': original['content']}]
        for filename in original.get('images', []):
            path = Path(filename)
            mime = mimetypes.guess_type(path.name)[0] or 'image/png'
            encoded = base64.b64encode(path.read_bytes()).decode('ascii')
            content.append({'type': 'input_image', 'image_url': f'data:{mime};base64,{encoded}', 'detail': 'high'})
        messages.append({'role': original['role'], 'content': content})
    options = kwargs.get('options', {})
    payload = dict(model=model, input=messages, temperature=options.get('temperature', 0),
                   max_output_tokens=options.get('num_predict', 4096), store=False)
    if kwargs.get('format'):
        payload['text'] = {'format': {'type': 'json_schema', 'name': 'registry_response',
                                      'strict': True, 'schema': strict_schema(kwargs['format'])}}
    request = Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode('utf-8'),
                      headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=300) as response:
            result = json.load(response)
    except HTTPError as error:
        # Do not expose response bodies, prompts, or credentials in errors/logs.
        hints = {401: 'Check the backend API key.', 403: 'Check model access.',
                 429: 'Check API quota/rate limits and retry.', 400: 'Check OPENAI_MODEL supports images, temperature and structured outputs.'}
        raise ProviderError(f'OpenAI HTTP {error.code}. ' + hints.get(error.code, 'Please retry.')) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError('OpenAI connection failed or timed out. Please retry.') from None
    if result.get('status') != 'completed':
        raise ProviderError('OpenAI response was incomplete. Please retry; no result was saved.')
    parts = [part for item in result.get('output', []) for part in item.get('content', [])]
    if any(part.get('type') == 'refusal' for part in parts):
        raise ProviderError('OpenAI declined this request. No result was saved.')
    content = '\n'.join(part['text'] for part in parts if part.get('type') == 'output_text')
    if not content.strip():
        raise ProviderError('OpenAI returned no text. Please retry.')
    return SimpleNamespace(message=SimpleNamespace(content=content), done_reason='stop')
