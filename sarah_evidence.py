"""Built-in Sarah evidence assistant: exact excerpts and revision comparisons.

Runs without a language model, network provider or key. This is bounded retrieval
and comparison, not general-purpose generated reasoning. Source text never drives
tool calls; all operations below are reads of the selected project's MCP snapshot.
"""
from __future__ import annotations
import difflib
import re

VERSION = 'sarah-evidence-1'
STOP = set('a an and are as at be been but by can could did do does for from has have how i in is it me my of on or our please say she show so some tell than that the their them there these they this those to us was we were what when where which who why will with would you your sarah about'.split())
GENERIC = set('source sources document documents evidence record records find finding findings explain answer brief briefing summarize summary overview know said says decision decisions current changed change changes compare comparison latest previous earlier approved approve approval'.split())
ALIASES = {
    'budget': {'cost', 'costs', 'spend', 'spending', 'price', 'prices', 'money', 'dollars'},
    'launch': {'release', 'released', 'launching'},
    'approval': {'approve', 'approved', 'signoff', 'signed'},
    'date': {'dates', 'deadline', 'deadlines', 'schedule', 'scheduled', 'when'},
    'risk': {'risks', 'blocked', 'blocker', 'blockers', 'wait', 'required', 'missing', 'pending'},
    'owner': {'owners', 'responsible', 'assigned', 'assignment'},
}


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def topics(question):
    result = words(question) - STOP - GENERIC
    for base, synonyms in ALIASES.items():
        if base in result or result & synonyms:
            result |= {base} | synonyms
    return result


def sentences(source):
    """Offsets preserve exact contiguous text, including punctuation and spacing."""
    for match in re.finditer(r'[^\n]+', source['text']):
        text = match.group().strip()
        if len(text) < 8:
            continue
        if len(text) > 650:
            # An explicit excerpt, never imply it is the whole sentence.
            text = text[:650]
            text = text[:text.rfind(' ')] if ' ' in text else text
        yield text


def content_sentences(source):
    """Keep factual wording for comparison, excluding standalone dated headings.

    Full original lines remain available in read_source and the exact diff.
    """
    heading = re.compile(r'(?:decision record|proposal|meeting notes|notes|revision|version)\s*(?:[—–:#-]\s*)?(?:[a-z]+\s+\d{1,2}(?:,?\s+\d{4})?|\d{4}-\d{2}-\d{2}|\d+)\s*', re.I)
    return [line for line in sentences(source) if not heading.fullmatch(line)]


def cite(source, quote):
    return {'source_id': source['id'], 'quote': quote}


def resolve_question(question, history):
    q = question.strip()
    followup = bool(re.search(r'\b(that|those|it|them|above|same)\b', q, re.I))
    evidence_followup = bool(re.fullmatch(
        r'(?:and\s+)?(?:why|which sources?|show (?:me )?(?:the )?(?:evidence|sources?|quotes?)|where (?:is|was) (?:the )?evidence)[?!. ]*', q, re.I))
    if history and (evidence_followup or (followup and not topics(q) - {'support', 'supported', 'prove', 'proof'})):
        # History supplies the topic only. Never treat an earlier conclusion as evidence.
        prior = history[0]
        topic = prior.get('topic_question') or prior['question']
        return topic, True
    return q, False


def prepare(context, question, history, client, trace):
    effective, followed = resolve_question(question, history)
    query = topics(effective)
    qwords = words(effective)
    all_sources = context['sources']
    overview = not query or bool(qwords & {'overview', 'summarize', 'summary', 'everything'})
    changed = bool(qwords & {'changed', 'changes', 'compare', 'comparison', 'difference', 'differences'})
    decisions = bool(qwords & {'decision', 'decisions', 'approved', 'approval', 'current'})
    unknowns = []
    if followed:
        trace.append({'operation': 'follow_up_topic', 'previous_briefing_id': history[0]['id'],
                      'uses_previous_conclusions_as_evidence': False})
    ranked = []
    relevant = []
    for source in all_sources:
        title_words = words(source['title'] + ' ' + source['document_key'])
        candidates = []
        for quote in content_sentences(source):
            score = len(query & words(quote)) * 3 + len(query & title_words)
            if overview or score:
                candidates.append((score, quote))
        if candidates:
            relevant.append(source)
            candidates.sort(key=lambda item: -item[0])
            for score, quote in candidates[:3]:
                ranked.append((score, source, quote))
    ranked.sort(key=lambda item: (-item[0], all_sources.index(item[1])))
    findings, conflicts, comparisons = [], [], []
    if changed:
        for after in relevant:
            parent_id = after.get('parent_source_id')
            before = next((s for s in all_sources if s['id'] == parent_id), None)
            if not before:
                continue
            result = client.call('compare_revisions', {'project_id': context['project']['id'],
                'before_id': before['id'], 'after_id': after['id']})
            trace.append({'tool': 'compare_revisions', 'before_id': before['id'], 'after_id': after['id']})
            comparisons.append({'document_key': after['document_key'], 'before': before['revision'],
                                'after': after['revision'], **result})
            before_lines, after_lines = content_sentences(before), content_sentences(after)
            removed = [line for line in before_lines if line not in after_lines]
            added = [line for line in after_lines if line not in before_lines]
            if removed and added and len(findings) < 4:
                findings.append({'text': f"{after['document_key']}: wording differs between {before['revision']} and {after['revision']}. The quoted passages show an earlier and a later wording; this does not establish approval.",
                    'citations': [cite(before, removed[0]), cite(after, added[0])]})
        if not comparisons:
            unknowns.append('No linked revisions were found for this topic. Add a revision to an existing document to compare its exact changes.')
    # Compare explicit decision-labelled records only within one document group.
    # Different wording is a review flag, never a claim that the newer record wins.
    if decisions or overview or changed:
        grouped = {}
        for source in relevant:
            if source['kind'] == 'decision':
                grouped.setdefault(source['document_key'], []).append(source)
        for group, values in grouped.items():
            for first, second in zip(values, values[1:]):
                left = content_sentences(first)
                right = content_sentences(second)
                pairs = [(difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio(), a, b)
                         for a in left for b in right if a != b and len(words(a) & words(b)) >= 3]
                if pairs and len(conflicts) < 4:
                    similarity, a, b = max(pairs, key=lambda item: item[0])
                    if similarity >= .40:
                        conflicts.append({'text': f"Possible disagreement in {group}: two records labelled as decisions contain different wording. Review the quotes and authority before treating either as current.",
                                          'certainty': 'possible', 'citations': [cite(first, a), cite(second, b)]})
    flagged = {(c['source_id'], c['quote']) for f in conflicts for c in f['citations']}
    findings = [f for f in findings if not all((c['source_id'], c['quote']) in flagged for c in f['citations'])]
    seen = flagged | {(c['source_id'], c['quote']) for f in findings for c in f['citations']}
    for score, source, quote in ranked:
        key = (source['id'], quote)
        if key in seen:
            continue
        seen.add(key)
        if len(findings) >= 6:
            break
        label = {'proposal': 'Proposal excerpt — not evidence of approval',
                 'decision': 'Excerpt from a record labelled as a decision',
                 'notes': 'Source excerpt'}[source['kind']]
        findings.append({'text': f"{label}: {source['title']} / {source['revision']}.",
                         'citations': [cite(source, quote)]})
    if not findings and not conflicts:
        unknowns = ['I could not find wording matching that question in this project. Try a document term, add the missing evidence, or ask for an overview.']
    elif decisions and not any(s['kind'] == 'decision' for s in relevant):
        unknowns.append('The matching sources are not labelled as decision records. Their contents do not establish a current approved decision.')
    if qwords & {'send', 'email', 'delete', 'approve', 'publish', 'sign'}:
        unknowns.append('This assistant has only read the evidence. It has not sent a message, changed a record, approved a decision or published anything.')
    return {'title': 'Sarah · ' + ('Revision review' if changed else 'Evidence for your question'),
            'findings': findings, 'conflicts': conflicts, 'unknowns': unknowns[:3],
            'topic_question': effective, 'answer_kind': 'excerpts' if findings or conflicts else 'abstention',
            'comparisons': comparisons, 'source_count': len(all_sources), 'matching_source_count': len(relevant),
            'next_questions': ['What changed in the revisions?', 'Which sources support that?', 'Give me an overview.']}
