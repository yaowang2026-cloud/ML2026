"""Local multi-photo extraction, human review and CSV API."""
from contextlib import contextmanager
import csv
import io
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4
from filelock import FileLock
from flask import Flask, jsonify, request, send_from_directory, abort, Response
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import HTTPException
try:
    from . import extraction as engine
except ImportError:
    import extraction as engine
ROOT = Path(__file__).resolve().parent.parent

def create_app(data_dir=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=int(os.getenv('MAX_UPLOAD_MB', '100')) * 1024 * 1024, MAX_FORM_PARTS=int(os.getenv('MAX_FORM_PARTS', '10000')))
    data = Path(data_dir or ROOT / 'work' / 'registry')
    data.mkdir(parents=True, exist_ok=True)
    database = data / 'sessions.sqlite3'
    lock = FileLock(str(data / 'registry.lock'))
    @contextmanager
    def connection():
        db = sqlite3.connect(database)
        try:
            with db:
                yield db
        finally:
            db.close()

    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL, saved INTEGER NOT NULL DEFAULT 0)')

    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS progress (id TEXT PRIMARY KEY, events TEXT NOT NULL, updated REAL NOT NULL)')

    def report(progress_id, message):
        if progress_id is None:
            return
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT events FROM progress WHERE id=?', (progress_id,)).fetchone()
            events = json.loads(row[0]) if row else []
            events.append(message)
            db.execute("INSERT OR REPLACE INTO progress VALUES (?, ?, unixepoch())", (progress_id, json.dumps(events)))

    @app.get('/api/progress/<progress_id>')
    def get_progress(progress_id):
        with connection() as db:
            row = db.execute('SELECT events FROM progress WHERE id=?', (progress_id,)).fetchone()
        if row is None:
            return jsonify(events=[]), 200
        return jsonify(events=json.loads(row[0]))

    def read_session(db, record_id):
        row = db.execute('SELECT payload, saved FROM sessions WHERE id=?', (record_id,)).fetchone()
        if row is None: abort(404, description='Dossier introuvable.')
        return json.loads(row[0]), bool(row[1])

    def export_csv(db):
        rows = db.execute('SELECT payload FROM sessions WHERE saved=1 ORDER BY rowid').fetchall()
        temporary = data / 'registry.csv.tmp'
        with temporary.open('w', newline='', encoding='utf-8-sig') as out:
            writer = csv.DictWriter(out, fieldnames=engine.TARGET_COLUMNS)
            writer.writeheader()
            for (raw,) in rows:
                writer.writerow({f['name']: engine.csv_value(f['value']) for f in json.loads(raw)['fields']})
        os.replace(temporary, data / 'registry.csv')

    def save_if_complete(db, session, saved=False):
        if not saved and engine.present(session)['ready_to_save']:
            db.execute('UPDATE sessions SET saved=1 WHERE id=?', (session['record_id'],))
            saved = True
        if saved:
            # Status and edits roll back together if the CSV cannot be replaced.
            export_csv(db)
        return saved

    def reconcile_completed_records():
        with lock, connection() as db:
            changed = False
            for record_id, payload in db.execute('SELECT id,payload FROM sessions WHERE saved=0').fetchall():
                session = json.loads(payload)
                if engine.present(session)['ready_to_save']:
                    session['revision'] += 1
                    db.execute('UPDATE sessions SET saved=1,payload=? WHERE id=?', (json.dumps(session), record_id))
                    changed = True
            if changed:
                export_csv(db)

    @app.errorhandler(HTTPException)
    def http_error(error): return jsonify(error=error.description), error.code

    @app.errorhandler(engine.pipeline.model_provider.ProviderError)
    def provider_error(error): return jsonify(error=str(error)), 503

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.error('Backend failure: %s', type(error).__name__)
        return jsonify(error='Le traitement a échoué. Vérifiez Ollama et réessayez. Aucun succès de sauvegarde confirmé.'), 503

    @app.get('/api/dataset')
    def dataset():
        status = request.args.get('status', 'saved')
        if status not in {'saved', 'draft'}:
            abort(400, description='Invalid dataset status.')
        offset = request.args.get('offset', 0, type=int)
        if offset is None or offset < 0:
            abort(400, description='Invalid offset.')
        with connection() as db:
            saved_count = db.execute('SELECT COUNT(*) FROM sessions WHERE saved=1').fetchone()[0]
            draft_count = db.execute('SELECT COUNT(*) FROM sessions WHERE saved=0').fetchone()[0]
            records = db.execute('SELECT id,payload FROM sessions WHERE saved=? ORDER BY rowid DESC LIMIT 100 OFFSET ?', (int(status == 'saved'), offset)).fetchall()
        rows = []
        for record_id, payload in records:
            session = json.loads(payload)
            rows.append(dict(record_id=record_id, revision=session['revision'], unresolved=sum(not f['resolved'] for f in session['fields']),
                             values={f['name']: f['value'] for f in session['fields']}))
        return jsonify(columns=engine.TARGET_COLUMNS, rows=rows, saved_count=saved_count, draft_count=draft_count,
                       total=saved_count if status == 'saved' else draft_count, offset=offset, limit=100)

    @app.post('/api/records/<record_id>/delete')
    def delete_record(record_id):
        body = request.get_json()
        if not isinstance(body, dict) or body.get('confirm') is not True:
            return jsonify(error='Deletion confirmation required.'), 400
        with lock, connection() as db:
            session, saved = read_session(db, record_id)
            if body.get('revision') != session['revision']:
                return jsonify(error='This record changed. Refresh the dataset before deleting.'), 409
            db.execute('DELETE FROM sessions WHERE id=?', (record_id,))
            if saved:
                # Roll back the deletion if the CSV cannot be replaced, e.g. open in Excel.
                export_csv(db)
        return jsonify(deleted=True, record_id=record_id)

    @app.post('/api/records/<record_id>/manual')
    def manual_edit(record_id):
        body = request.get_json()
        if not isinstance(body, dict) or not isinstance(body.get('changes'), dict):
            return jsonify(error='Expected a changes object.'), 400
        changes = body['changes']
        if not changes or set(changes) - set(engine.TARGET_COLUMNS):
            return jsonify(error='Choose at least one valid field to update or confirm.'), 422
        cleaned = {}
        for name, value in changes.items():
            try:
                cleaned[name] = engine.parse_manual_value(name, value)
            except ValueError as error:
                return jsonify(error=f'{name}: {error}', field=name, expected=engine.FIELD_RULES[name]), 422
        with lock, connection() as db:
            session, saved = read_session(db, record_id)
            if body.get('revision') != session['revision']:
                return jsonify(error='This record changed. Cancel and reopen the editor before saving.'), 409
            if not engine.patient_id_confirmed(session) and 'id' not in cleaned:
                return jsonify(error='Confirm the patient ID first.'), 422
            for field in session['fields']:
                if field['name'] in cleaned:
                    if field['name'] == 'id': field['user_confirmed'] = True
                    field.update(value=cleaned[field['name']], resolved=True,
                                 status='KNOWN' if cleaned[field['name']] is not None else 'NOT_PROVIDED',
                                 reason='Manually verified by user.', question=None, user_response=changes[field['name']])
            session['revision'] += 1
            db.execute('UPDATE sessions SET payload=? WHERE id=?', (json.dumps(session), record_id))
            saved = save_if_complete(db, session, saved)
        return jsonify(engine.present(session, saved))

    @app.get('/api/dataset.csv')
    def download_dataset():
        with connection() as db:
            records = db.execute('SELECT payload FROM sessions WHERE saved=1 ORDER BY rowid').fetchall()
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=engine.TARGET_COLUMNS)
        writer.writeheader()
        for (payload,) in records:
            writer.writerow({f['name']: engine.csv_value(f['value']) for f in json.loads(payload)['fields']})
        return Response('\ufeff' + output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="registry.csv"', 'Cache-Control': 'no-store'})

    @app.get('/api/health')
    def health(): return jsonify(ok=True, model=engine.pipeline.MODEL)

    @app.post('/api/extract')
    def extract():
        provider = request.form.get('provider', 'local')
        if provider not in {'local', 'openai'}:
            return jsonify(error='Unknown model provider.'), 400
        model = engine.pipeline.model_provider.online_model() if provider == 'openai' else engine.pipeline.MODEL
        files = request.files.getlist('images') or request.files.getlist('image')
        if not files: return jsonify(error='Ajoutez au moins une photo.'), 400
        progress_id = request.form.get('progress_id')
        if progress_id is not None and not re.fullmatch(r'[a-f0-9-]{36}', progress_id):
            return jsonify(error='Identifiant de progression invalide.'), 400
        if progress_id:
            with connection() as db:
                db.execute('DELETE FROM progress WHERE updated < unixepoch() - 86400')
                try:
                    db.execute("INSERT INTO progress VALUES (?, '[]', unixepoch())", (progress_id,))
                except sqlite3.IntegrityError:
                    return jsonify(error='Cette analyse a déjà été lancée.'), 409
        report(progress_id, f'{len(files)} photo(s) reçue(s). Préparation des images…')
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for index, file in enumerate(files):
                try:
                    with Image.open(file.stream) as photo:
                        if photo.format not in {'JPEG', 'PNG', 'WEBP'}: raise ValueError('Format non pris en charge.')
                        photo.load()
                        path = Path(folder) / f'page-{index + 1}.png'
                        photo.convert('RGB').save(path)
                        paths.append(path)
                except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                    return jsonify(error=f'Page {index + 1}: image invalide. Utilisez JPEG, PNG ou WebP.'), 400
            try:
                with engine.pipeline.model_provider.use_provider(provider, model):
                    fields = engine.extract_images(paths, progress=lambda message: report(progress_id, message))
            except ValueError as error: return jsonify(error=str(error)), 422
        session = dict(record_id=uuid4().hex, revision=0, page_count=len(files), fields=fields, model_provider=provider, model_name=model)
        with lock, connection() as db:
            db.execute('INSERT INTO sessions(id,payload) VALUES (?,?)', (session['record_id'], json.dumps(session)))
        report(progress_id, 'Analyse terminée. Les champs sont prêts à être vérifiés.')
        with connection() as db:
            row = db.execute('SELECT events FROM progress WHERE id=?', (progress_id,)).fetchone()
        return jsonify({**engine.present(session), 'progress_events': json.loads(row[0]) if row else []})

    @app.get('/api/records/<record_id>')
    def get_record(record_id):
        with connection() as db: session, saved = read_session(db, record_id)
        return jsonify(engine.present(session, saved))

    @app.post('/api/records/<record_id>/review')
    def review(record_id):
        body = request.get_json()
        if not isinstance(body, dict): return jsonify(error='Un objet JSON est requis.'), 400
        with connection() as db: session, saved = read_session(db, record_id)
        if saved or body.get('revision') != session['revision']: return jsonify(error='Dossier enregistré ou modifié. Rechargez le dossier.'), 409
        field = next((f for f in session['fields'] if f['name'] == body.get('field')), None)
        if field is None: return jsonify(error='Champ inconnu.'), 400
        if field['name'] != 'id' and not engine.patient_id_confirmed(session):
            return jsonify(error='Confirm the patient ID first.'), 422
        try:
            with engine.pipeline.model_provider.use_provider(session.get('model_provider', 'local'), session.get('model_name')):
                engine.apply_review(field, body.get('action'), body.get('response'))
        except ValueError as error: return jsonify(error=str(error)), 422
        with lock, connection() as db:
            latest, saved = read_session(db, record_id)
            if saved or latest['revision'] != session['revision']: return jsonify(error='Le dossier a changé. Rechargez-le.'), 409
            session['revision'] += 1
            db.execute('UPDATE sessions SET payload=? WHERE id=?', (json.dumps(session), record_id))
            saved = save_if_complete(db, session)
        return jsonify(engine.present(session, saved))

    @app.post('/api/records/<record_id>/finalize')
    def finalize(record_id):
        body = request.get_json()
        if not isinstance(body, dict) or body.get('confirm') is not True: return jsonify(error='Confirmation finale requise.'), 400
        with lock:
            with connection() as db:
                session, saved = read_session(db, record_id)
                if not saved:
                    if body.get('revision') != session['revision']: return jsonify(error='Rechargez la version actuelle.'), 409
                    if not engine.patient_id_confirmed(session):
                        return jsonify(error='A confirmed patient ID is required before saving.'), 422
                    if any(not f['resolved'] for f in session['fields']): return jsonify(error='Confirmez, corrigez ou laissez explicitement vide chaque champ à vérifier/manquant.'), 422
                    db.execute('UPDATE sessions SET saved=1 WHERE id=?', (record_id,))
            with connection() as db: export_csv(db)
        return jsonify(record_id=record_id, saved=True, message='Dossier enregistré dans registry.csv.', csv='work/registry/registry.csv')

    @app.get('/')
    def index(): return send_from_directory(ROOT, 'index.html')

    @app.get('/<filename>')
    def assets(filename):
        if filename not in {'app.js', 'style.css'}: abort(404)
        return send_from_directory(ROOT, filename)
    reconcile_completed_records()
    return app

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5001, debug=False)
