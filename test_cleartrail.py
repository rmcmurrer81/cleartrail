import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from companion import MCPClient
from evidence import EvidenceStore
from server import create_server


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EvidenceStore(self.temp.name)
        self.pid = self.store.create_project('A film launch')['id']
        self.a = self.add('v1', 'Mira approved the June 12 launch. Final client approval is still required.')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def add(self, revision, text, **kwargs):
        return self.store.import_document(self.pid, 'Launch plan', revision, 'Launch', text=text, **kwargs)['source']

    def draft(self):
        return {'title':'Launch approval', 'findings':[{'text':'Mira approved June 12, while final client approval remains required.',
            'citations':[{'source_id':self.a['id'],'quote':self.a['text']}]}], 'conflicts':[], 'unknowns':[]}

    def save(self, draft=None, snapshot=None):
        return self.store.save_briefing(self.pid, snapshot or self.store.list_sources(self.pid)['snapshot_sha256'],
            'What was approved?', draft or self.draft(), {'name':'test','real_model_call':False}, [])

    def test_revisions_are_immutable_and_duplicate_retry_is_idempotent(self):
        duplicate=self.add('v1',self.a['text'])
        self.assertEqual(duplicate['id'],self.a['id'])
        with self.assertRaisesRegex(ValueError,'revision label'):
            self.add('v1','Different decision with the same label.')
        self.add('v2','Proposed June 13; not yet approved.',parent_source_id=self.a['id'])
        self.assertEqual(len(self.store.list_sources(self.pid)['sources']),2)
        self.assertEqual(self.store.read_source(self.pid,self.a['id'])['source']['text'],self.a['text'])

    def test_project_sources_do_not_leak(self):
        other=self.store.create_project('Separate project')['id']
        self.assertEqual(self.store.list_sources(other)['sources'],[])
        with self.assertRaises(ValueError):
            self.store.read_source(other,self.a['id'])
        with self.assertRaisesRegex(ValueError,'at least one'):
            self.store.get_context(other,'What was decided?')

    def test_search_and_compare_show_exact_evidence(self):
        b=self.add('v2','Proposed June 13; not yet approved.',parent_source_id=self.a['id'])
        found=self.store.search_evidence(self.pid,'client approval')
        self.assertEqual(found['matches'][0]['quote'],self.a['text'])
        difference=self.store.compare_revisions(self.pid,self.a['id'],b['id'])
        self.assertIn('-'+self.a['text'],difference['diff'])
        self.assertIn('+Proposed June 13',difference['diff'])

    def test_fabricated_quote_is_rejected_without_saving(self):
        draft=self.draft();draft['findings'][0]['citations'][0]['quote']='The launch is definitely approved.'
        with self.assertRaisesRegex(ValueError,'not in the selected sources'):
            self.save(draft)
        self.assertEqual(self.store.list_briefings(self.pid)['briefings'],[])

    def test_conflict_requires_two_distinct_sources(self):
        draft=self.draft();draft['conflicts']=copy.deepcopy(draft['findings'])
        with self.assertRaisesRegex(ValueError,'two distinct'):
            self.save(draft)

    def test_stray_model_field_name_cannot_be_saved_as_uncertainty(self):
        draft=self.draft();draft['unknowns']=['citations']
        with self.assertRaisesRegex(ValueError,'incomplete uncertainty'):
            self.save(draft)
        self.assertEqual(self.store.list_briefings(self.pid)['briefings'],[])

    def test_duplicate_cannot_hide_cross_project_parent(self):
        other=self.store.create_project('Other project')['id']
        foreign=self.store.import_document(other,'Other','1','Launch',text='A different project source.')['source']
        with self.assertRaises(ValueError):
            self.add('v1',self.a['text'],parent_source_id=foreign['id'])

    def test_changed_sources_do_not_save_a_stale_answer(self):
        snapshot=self.store.list_sources(self.pid)['snapshot_sha256']
        self.add('v2','The revised plan has a different date.')
        with self.assertRaisesRegex(ValueError,'Sources changed'):
            self.save(snapshot=snapshot)

    def test_supported_briefing_restores_and_exports_exact_quotes(self):
        saved=self.save()['briefing']
        self.store.close();self.store=EvidenceStore(self.temp.name)
        restored=self.store.list_briefings(self.pid)['briefings'][0]
        self.assertEqual(restored['id'],saved['id'])
        self.assertTrue(restored['exact_quotes_verified'])
        result=self.store.export_briefing(self.pid,saved['id'])
        self.assertIn(self.a['text'],result['markdown'])
        self.assertTrue((Path(self.temp.name)/'exports'/result['filename']).is_file())

    def test_tampered_database_payload_is_not_trusted(self):
        self.store.db.execute('UPDATE sources SET payload=? WHERE id=?',('tampered',self.a['id']))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError,'integrity'):
            self.store.list_sources(self.pid)

    def test_prior_briefing_is_labeled_outdated_after_new_evidence(self):
        saved=self.save()['briefing']
        self.assertFalse(self.store.list_briefings(self.pid)['briefings'][0]['source_snapshot_outdated'])
        self.add('v2','A new decision record changes the proposed date.')
        self.assertTrue(self.store.list_briefings(self.pid)['briefings'][0]['source_snapshot_outdated'])
        self.assertIn('Source set changed',self.store.export_briefing(self.pid,saved['id'])['markdown'])

    def test_real_uploaded_text_round_trip(self):
        raw=b'Budget decision: keep the prototype below 900 dollars.\nNo cloud provision is authorized.'
        source=self.store.import_document(self.pid,'Budget','1','Budget',filename='../budget.txt',
            content_base64=base64.b64encode(raw).decode())['source']
        self.assertEqual(source['text'],raw.decode())
        self.assertEqual(source['filename'],'budget.txt')
        self.assertEqual((Path(self.temp.name)/'attachments'/source['raw_sha256']).read_bytes(),raw)

    def test_blank_pdf_gives_an_actionable_error(self):
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=200,height=200)
        stream=io.BytesIO();writer.write(stream)
        with self.assertRaisesRegex(ValueError,'No readable text'):
            self.store.import_document(self.pid,'Scanned','1','Scanned',filename='scan.pdf',
                content_base64=base64.b64encode(stream.getvalue()).decode())


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=create_server(0,self.temp.name)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/mcp'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server.store.close();self.temp.cleanup()

    def test_real_mcp_initialize_call_read_and_session_close(self):
        client=MCPClient(self.url,self.server.local_token)
        self.assertEqual(client.rpc('tools/list')['tools'][0]['name'],'list_projects')
        pid=client.call('create_project',{'name':'MCP input'})['id']
        client.call('import_document',{'project_id':pid,'title':'Evidence','revision':'1','document_key':'Brief',
            'text':'A real MCP call saved this source. No model was involved in this engineering test.'})
        context=client.call('get_context',{'project_id':pid,'question':'What was saved?'})
        self.assertEqual(len(context['sources']),1)
        client.close()
        with self.assertRaises(urllib.error.HTTPError) as error:
            client.rpc('tools/list')
        self.assertEqual(error.exception.code,404)
        error.exception.close()

    def test_wrong_token_and_origin_are_rejected(self):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for headers,code in [({'Authorization':'Bearer wrong'},401),
            ({'Authorization':'Bearer '+self.server.local_token,'Origin':'https://external.example'},403)]:
            request=urllib.request.Request(self.url,data=b'{}',headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as error:
                opener.open(request)
            self.assertEqual(error.exception.code,code)
            error.exception.close()


if __name__=='__main__':unittest.main()
