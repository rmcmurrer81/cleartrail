"""Conversation and onboarding that work before a document has been added."""
import json
import re
import uuid
from datetime import datetime, timezone


def help_reply(question, source_count):
    q = question.casefold().strip().rstrip('?.!')
    if re.fullmatch(r'(hi|hello|hey|good morning|good evening)( sarah)?', q):
        return "Hi, I'm Sarah. Tell me what you're working on. I can help you keep track of what changed, find the source behind a claim, and compare decisions. What would you like to work through?"
    if re.search(r'(about yourself|who are you|what (?:can|do) you do|your name|introduce yourself)', q):
        return "I'm Sarah, your evidence assistant in ClearTrail. I help you compare document revisions and find the exact words behind a decision. I keep disagreements visible and tell you when evidence is missing. Our conversation uses no credits."
    if re.search(r'(where (?:should|do|can) (?:we|i) (?:start|begin)|how (?:do|can) i (?:start|begin|use)|get started|help me start|what should i do|what next)', q):
        if source_count:
            return "Let's start with the question you need answered. You already have sources here. Try asking what changed, what is still awaiting approval, or which source supports a decision. I will keep the relevant quotes beside the answer."
        return "Start with one thing you need to understand: a changed date, a budget, or a decision. You can add a document or paste your notes. Tell me about it here first if you prefer, then use Save as evidence to keep your exact wording."
    if re.search(r'(hear you|your voice|can you speak|talk (?:out loud|to me)|no sound|play.*voice)', q):
        return "Use Turn voice on beside my portrait. I can then speak my replies in the voice Robert approved. Preparing speech runs on this computer and uses no credits. You can pause or replay it whenever you like."
    if re.search(r'(cost|credits|free|pay|api key|model)', q) and re.search(r'(you|sarah|cleartrail|this|need|use|require)', q):
        return "Talking with me, checking your saved evidence and exporting a briefing do not use credits or require an API key. ClearTrail's optional local-model mode is separate. My custom voice uses the included optional voice pack."
    if re.fullmatch(r'(thanks|thank you|thank you sarah|ok|okay|great|good)', q):
        return "You're welcome. Tell me the next question, or choose a source to read or compare."
    if not source_count:
        return "I can help you work through that. I don't have any source material in this project yet. You can keep this message with Save as evidence, add a document, or tell me what decision you're trying to understand."
    return None


def history(store, project_id):
    with store.lock:
        store.db.execute('CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL)')
        store.db.commit()
        return [json.loads(row['payload']) for row in store.db.execute(
            'SELECT payload FROM conversations WHERE project_id=? ORDER BY rowid DESC LIMIT 16', (project_id or '',))][::-1]


def remember(store, project_id, question, reply, briefing_id=None):
    with store.lock:
        history(store, project_id)
        entry = {'id': uuid.uuid4().hex, 'question': question, 'reply': reply,
                 'created_at': datetime.now(timezone.utc).isoformat(), 'briefing_id': briefing_id}
        store.db.execute('INSERT INTO conversations VALUES(?,?,?)', (entry['id'], project_id or '', json.dumps(entry)))
        store.db.commit()
        return entry


def summary(briefing):
    if briefing.get('answer_kind') == 'abstention' and briefing.get('unknowns') and not briefing.get('conflicts'):
        return briefing['unknowns'][0]
    if briefing['conflicts']:
        return "I found different wording in records labelled as decisions. I've kept both sides visible. Review the exact quotes and the revision comparison before choosing which decision applies."
    first = next((c['quote'] for f in briefing['findings'] for c in f['citations']), None)
    prefix = f"I checked {briefing.get('source_count', 'the saved')} sources. "
    if first and len(first) <= 250:
        return prefix + 'One matching excerpt says: ' + first
    return prefix + 'The matching passages are below. Select a quote to see it in the original source.'
