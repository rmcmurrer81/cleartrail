"""ClearTrail: immutable source revisions and traceable document briefings."""
from __future__ import annotations
import base64
import difflib
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import threading
from datetime import datetime, timezone
import uuid


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def clean(value, label, maximum=200):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError(f'{label} must contain 1 to {maximum} characters.')
    return value.strip()


def now():
    return datetime.now(timezone.utc).isoformat()


class EvidenceStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.folder / 'cleartrail.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),
            payload TEXT NOT NULL,digest TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS briefings(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),
            payload TEXT NOT NULL,digest TEXT NOT NULL);
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def project(self, project_id):
        row = self.db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        if not row:
            raise ValueError('Choose an existing project.')
        return dict(row)

    def list_projects(self):
        with self.lock:
            return {'projects': [dict(r) for r in self.db.execute('SELECT * FROM projects ORDER BY created')]}

    def create_project(self, name):
        name = clean(name, 'Project name', 100)
        with self.lock:
            pid = uuid.uuid4().hex[:16]
            self.db.execute('INSERT INTO projects VALUES(?,?,?)', (pid, name, now()))
            self.db.commit()
            return self.project(pid)

    def import_document(self, project_id, title, revision, document_key, kind='notes', text=None,
                        filename=None, content_base64=None, parent_source_id=None):
        title, revision, document_key = [clean(v, label) for v, label in
            ((title, 'Title'), (revision, 'Revision'), (document_key, 'Document group'))]
        if kind not in ('decision', 'proposal', 'notes'):
            raise ValueError('Choose decision, proposal, or notes.')
        pages = []
        if content_base64 is not None:
            if text is not None:
                raise ValueError('Provide pasted text or a file, not both.')
            raw = base64.b64decode(content_base64, validate=True)
            if not 1 <= len(raw) <= 5 * 1024 * 1024:
                raise ValueError('Use a text or PDF file smaller than 5 MB.')
            suffix = Path(filename or '').suffix.lower()
            if suffix == '.pdf':
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(raw))
                if reader.is_encrypted or len(reader.pages) > 100:
                    raise ValueError('Use an unencrypted PDF of at most 100 pages.')
                pieces, offset = [], 0
                for number, page in enumerate(reader.pages, 1):
                    part = page.extract_text() or ''
                    pages.append({'page': number, 'start': offset, 'end': offset + len(part)})
                    pieces.append(part)
                    offset += len(part) + 2
                text = '\n\n'.join(pieces)
            elif suffix in ('.txt', '.md'):
                text = raw.decode('utf-8-sig')
            else:
                raise ValueError('Attach a PDF, UTF-8 text, or Markdown file.')
        else:
            text = clean(text, 'Document text', 80000)
            raw = text.encode('utf-8')
        if not text or not text.strip():
            raise ValueError('No readable text was found. Scanned PDFs need OCR before import.')
        if len(text) > 80000:
            raise ValueError('Use a document excerpt of at most 80,000 characters.')
        with self.lock:
            self.project(project_id)
            if parent_source_id:
                parent = self.read_source(project_id, parent_source_id)['source']
                if parent['document_key'] != document_key:
                    raise ValueError('A revision must stay in the same document group.')
            for existing in self.list_sources(project_id)['sources']:
                if existing['document_key'] == document_key and existing['revision'] == revision:
                    if (existing['text'] == text and existing['kind'] == kind and existing['title'] == title
                        and existing['raw_sha256'] == sha(raw) and existing['parent_source_id'] == parent_source_id):
                        return {'source': existing, 'previous_revisions_preserved': True, 'unchanged': True}
                    raise ValueError('That revision label already contains different content. Use a new revision label; the original is preserved.')
            source = {'id': uuid.uuid4().hex[:16], 'project_id': project_id, 'title': title,
                'revision': revision, 'document_key': document_key, 'kind': kind,
                'text': text, 'pages': pages, 'raw_sha256': sha(raw), 'text_sha256': sha(text),
                'filename': Path(filename).name if filename else None,
                'parent_source_id': parent_source_id, 'created_at': now()}
            payload = stable(source)
            # Raw attachments use content-addressed names; no user filename becomes a path.
            raw_folder = self.folder / 'attachments'
            raw_folder.mkdir(exist_ok=True)
            raw_path = raw_folder / source['raw_sha256']
            if not raw_path.exists():
                raw_path.write_bytes(raw)
            self.db.execute('INSERT INTO sources VALUES(?,?,?,?)',
                            (source['id'], project_id, payload, sha(payload)))
            self.db.commit()
            return {'source': source, 'previous_revisions_preserved': True}

    def _verified(self, row):
        if row is None or sha(row['payload']) != row['digest']:
            raise ValueError('Record unavailable or its saved integrity check failed.')
        return json.loads(row['payload'])

    def read_source(self, project_id, source_id):
        with self.lock:
            row = self.db.execute('SELECT * FROM sources WHERE id=? AND project_id=?',
                                  (source_id, project_id)).fetchone()
            return {'source': self._verified(row)}

    def list_sources(self, project_id):
        with self.lock:
            self.project(project_id)
            values = [self._verified(r) for r in self.db.execute(
                'SELECT * FROM sources WHERE project_id=? ORDER BY rowid', (project_id,))]
            return {'sources': values, 'snapshot_sha256': sha(stable(values))}

    def search_evidence(self, project_id, query, limit=12):
        query = clean(query, 'Search query', 500)
        if not isinstance(limit, int) or not 1 <= limit <= 30:
            raise ValueError('Search limit must be 1 to 30.')
        terms = set(re.findall(r'[\w-]+', query.casefold()))
        hits = []
        for source in self.list_sources(project_id)['sources']:
            for match in re.finditer(r'[^\n]+', source['text']):
                line = match.group()
                score = sum(1 for term in terms if term in line.casefold())
                if score:
                    hits.append({'source_id': source['id'], 'title': source['title'],
                        'revision': source['revision'], 'kind': source['kind'], 'quote': line,
                        'line': source['text'][:match.start()].count('\n') + 1, 'score': score})
        hits.sort(key=lambda h: (-h['score'], h['title'], h['line']))
        return {'matches': hits[:limit], 'total_matches': len(hits), 'query': query}

    def compare_revisions(self, project_id, before_id, after_id):
        before = self.read_source(project_id, before_id)['source']
        after = self.read_source(project_id, after_id)['source']
        if before['document_key'] != after['document_key']:
            raise ValueError('Choose revisions from the same document group.')
        lines = list(difflib.unified_diff(before['text'].splitlines(), after['text'].splitlines(),
                     fromfile=before['revision'], tofile=after['revision'], lineterm=''))
        return {'before_id': before_id, 'after_id': after_id, 'diff': '\n'.join(lines),
                'authority_note': 'A newer revision or proposal does not automatically supersede an earlier decision.'}

    def get_context(self, project_id, question):
        current = self.list_sources(project_id)
        if not current['sources']:
            raise ValueError('Add at least one source before asking for a briefing.')
        # Keep all revisions in a small project. Refuse oversized context rather than silently omit opposing records.
        if len(current['sources']) > 16 or sum(len(s['text']) for s in current['sources']) > 30000:
            raise ValueError('This project exceeds the current briefing limit of 16 revisions / 30,000 characters. Create a focused project with the relevant excerpts. Search and revision comparison still work.')
        return {**current, 'project': self.project(project_id), 'question': question,
                'authority_note': 'Kinds and revision labels are supplied by the user. Newer does not mean approved. Preserve conflicting decisions unless a source explicitly resolves them.'}

    def save_briefing(self, project_id, snapshot_sha256, question, draft, model, tool_trace):
        with self.lock:
            current = self.list_sources(project_id)
            if current['snapshot_sha256'] != snapshot_sha256:
                raise ValueError('Sources changed while the briefing was being prepared. Ask again with the updated evidence.')
            by_id = {s['id']: s for s in current['sources']}
            verified_claims = []
            for category in ('findings', 'conflicts'):
                entries = draft.get(category, [])
                if not isinstance(entries, list) or len(entries) > 8:
                    raise ValueError('The AI returned an unusable briefing structure.')
                for entry in entries:
                    clean(entry.get('text'), 'Briefing statement', 1500)
                    citations = entry.get('citations', [])
                    if not citations or len(citations) > 5:
                        raise ValueError('The AI omitted supporting quotes. No briefing was saved.')
                    for citation in citations:
                        source = by_id.get(citation.get('source_id'))
                        quote = citation.get('quote')
                        if not source or not isinstance(quote, str) or not 8 <= len(quote) <= 700 or quote not in source['text']:
                            raise ValueError('The AI cited wording that is not in the selected sources. No briefing was saved; try a narrower question.')
                        offset = source['text'].find(quote)
                        citation.update(title=source['title'], revision=source['revision'],
                            source_sha256=source['text_sha256'], line=source['text'][:offset].count('\n') + 1,
                            page=next((p['page'] for p in source['pages'] if p['start'] <= offset < p['end']), None))
                    if category == 'conflicts' and len({c['source_id'] for c in citations}) < 2:
                        raise ValueError('A conflict must cite at least two distinct source records.')
                    verified_claims.append(entry)
            if not verified_claims and not (model.get('provider') == 'builtin_evidence' and draft.get('answer_kind') == 'abstention' and draft.get('unknowns')):
                raise ValueError('The AI did not produce a supported finding. Try a more specific question.')
            unknowns = draft.get('unknowns', [])
            if (not isinstance(unknowns, list) or len(unknowns) > 3 or any(
                not isinstance(x, str) or not 20 <= len(x) <= 500 or len(re.findall(r'\w+', x)) < 4
                for x in unknowns)):
                raise ValueError('The AI returned an incomplete uncertainty note. No briefing was saved; ask again with a focused question.')
            briefing = {'id': uuid.uuid4().hex[:16], 'project_id': project_id, 'question': question,
                'title': clean(draft.get('title'), 'Briefing title', 200),
                'findings': draft.get('findings', []), 'conflicts': draft.get('conflicts', []),
                'unknowns': unknowns, 'snapshot_sha256': snapshot_sha256, 'model': model,
                'tool_trace': tool_trace, 'created_at': now(), 'exact_quotes_verified': True,
                'interpretation_note': ('Sarah selected exact excerpts and compared saved text without a language model. These are source records, not independent verification or a ruling on authority.' if model.get('provider') == 'builtin_evidence' else 'Quotes match the saved sources. Conclusions remain AI interpretations; source labels do not establish authority.')}
            if model.get('provider') == 'builtin_evidence':
                briefing.update(topic_question=draft.get('topic_question', question),
                    answer_kind=draft.get('answer_kind'), comparisons=draft.get('comparisons', []),
                    source_count=draft.get('source_count', 0), matching_source_count=draft.get('matching_source_count', 0),
                    next_questions=draft.get('next_questions', []))
            payload = stable(briefing)
            self.db.execute('INSERT INTO briefings VALUES(?,?,?,?)',
                            (briefing['id'], project_id, payload, sha(payload)))
            self.db.commit()
            return {'briefing': briefing}

    def list_briefings(self, project_id):
        with self.lock:
            self.project(project_id)
            current = self.list_sources(project_id)['snapshot_sha256']
            values = [self._verified(r) for r in self.db.execute(
                'SELECT * FROM briefings WHERE project_id=? ORDER BY rowid DESC', (project_id,))]
            for value in values:
                value['source_snapshot_outdated'] = value['snapshot_sha256'] != current
            return {'briefings': values}

    def export_briefing(self, project_id, briefing_id):
        with self.lock:
            row = self.db.execute('SELECT * FROM briefings WHERE id=? AND project_id=?',
                                  (briefing_id, project_id)).fetchone()
            value = self._verified(row)
        lines = ['# ' + value['title'], '', value['question'], '', value['interpretation_note'], '']
        if value['snapshot_sha256'] != self.list_sources(project_id)['snapshot_sha256']:
            lines += ['Source set changed after this briefing. It may omit later records; prepare a fresh briefing for the current decision.', '']
        for category in ('findings', 'conflicts'):
            if value[category]:
                lines += ['## ' + category.title(), '']
            for entry in value[category]:
                lines += [entry['text'], '']
                for c in entry['citations']:
                    where = f"page {c['page']}" if c['page'] else f"line {c['line']}"
                    lines += [f"> {c['quote']}", f"Source: {c['title']} / {c['revision']} / {where} / {c['source_id']}", '']
        if value['unknowns']:
            lines += ['## Unresolved', ''] + ['- ' + x for x in value['unknowns']]
        for comparison in value.get('comparisons', []):
            lines += ['', '## Exact revision comparison', '', comparison['document_key'] + ': ' + comparison['before'] + ' → ' + comparison['after'], '', '```diff', comparison['diff'], '```', '']
        lines += ['', 'Source snapshot SHA-256: ' + value['snapshot_sha256'], 'Prepared: ' + value['created_at']]
        markdown = '\n'.join(lines) + '\n'
        folder = self.folder / 'exports'
        folder.mkdir(exist_ok=True)
        filename = value['id'] + '.md'
        (folder / filename).write_text(markdown, encoding='utf-8')
        return {'filename': filename, 'markdown': markdown, 'sha256': sha(markdown)}

    def call(self, name, arguments):
        allowed = {row[0] for row in TOOLS}
        if name not in allowed or not isinstance(arguments, dict):
            raise ValueError('Unknown tool or invalid arguments.')
        return getattr(self, name)(**arguments)


def schema(properties, required):
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}


S = {'type': 'string'}
P = {'project_id': S}
TOOLS = [
 ('list_projects', 'List separate evidence projects.', schema({}, []), True),
 ('create_project', 'Create a separate evidence project.', schema({'name': S}, ['name']), False),
 ('import_document', 'Save an immutable text/PDF source revision; preserve previous versions.',
  schema({**P, 'title': S, 'revision': S, 'document_key': S, 'kind': {'type': 'string', 'enum': ['notes','proposal','decision']},
          'text': S, 'filename': S, 'content_base64': S, 'parent_source_id': S},
          ['project_id','title','revision','document_key']), False),
 ('list_sources', 'List verified source revisions in one project.', schema(P, ['project_id']), True),
 ('read_source', 'Read one exact saved source in its project.', schema({**P,'source_id':S}, ['project_id','source_id']), True),
 ('search_evidence', 'Find exact source lines matching query words.', schema({**P,'query':S,'limit':{'type':'integer'}}, ['project_id','query']), True),
 ('compare_revisions', 'Return exact text changes, without inferring approval.', schema({**P,'before_id':S,'after_id':S}, ['project_id','before_id','after_id']), True),
 ('get_context', 'Read a complete bounded source snapshot for a briefing.', schema({**P,'question':S}, ['project_id','question']), True),
 ('list_briefings', 'Restore saved evidence briefings.', schema(P,['project_id']), True),
 ('export_briefing', 'Save the selected briefing as a Markdown file.', schema({**P,'briefing_id':S}, ['project_id','briefing_id']), False),
]
