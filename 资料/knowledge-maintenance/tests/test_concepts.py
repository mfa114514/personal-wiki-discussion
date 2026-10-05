"""Check real behavior of pending entries and bounded source edits."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from analyze import run, write_owned
from concepts import discover_concepts
from link_concepts import apply_preview, prepare
from markdown_notes import parse_note


class ConceptTrial(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp.name)
        self.source = self.vault / 'courses'
        self.task = self.vault / 'tools' / 'tasks' / 'trial'
        self.source.mkdir()
        self.task.mkdir(parents=True)
        self.note = self.source / 'Lecture.md'
        self.note.write_text('# Lecture\n\nInfoNCE uses softmax.\n\n[missing code](absent.py)', encoding='utf-8')
        self.config = self.task / 'config.json'
        self.config.write_text(json.dumps({'vault':'../../../', 'source':'courses', 'concept_selection':'selection.json'}), encoding='utf-8')
        self.selection = {'source':'courses/Lecture.md', 'selection_method':'AI reading; verify evidence', 'concepts':[{'title':'InfoNCE', 'group':'方法', 'forms':['InfoNCE']}, {'title':'Softmax', 'group':'工具', 'forms':['softmax']}]}
        self.save_selection()

    def tearDown(self):
        self.temp.cleanup()

    def save_selection(self):
        (self.task / 'selection.json').write_text(json.dumps(self.selection, ensure_ascii=False), encoding='utf-8')

    def index(self):
        return json.loads((self.task / 'index.json').read_text(encoding='utf-8'))

    def test_missing_concepts_are_valid_but_missing_resource_remains_a_problem(self):
        prepare(self.config)
        apply_preview(self.config)
        result = run(self.config)
        self.assertEqual(result['link_statuses']['pending_concept'], 2)
        self.assertEqual(result['link_statuses']['missing_local_file'], 1)
        self.assertNotIn('unlinked_mentions', self.index())
        self.assertEqual(len(self.index()['concepts']), 2)

    def test_entry_created_elsewhere_updates_unchanged_source_reference(self):
        prepare(self.config)
        apply_preview(self.config)
        run(self.config)
        entries = self.vault / 'entries'
        entries.mkdir()
        (entries / 'InfoNCE.md').write_text('# InfoNCE\n\nAn explanation.', encoding='utf-8')
        result = run(self.config)
        self.assertEqual(result['stats']['parsed'], 0)
        reference = next(e for e in self.index()['concept_references'] if e['target'] == 'InfoNCE')
        self.assertEqual(reference['resolved'], 'entries/InfoNCE.md')
        self.assertEqual(self.index()['backlinks']['entries/InfoNCE.md'][0]['source'], 'courses/Lecture.md')
        incremental = self.index()
        run(self.config, force=True)
        self.assertEqual(incremental, self.index())

    def test_duplicate_entry_names_are_not_silently_chosen(self):
        for directory in ('one', 'two'):
            folder = self.vault / directory
            folder.mkdir()
            (folder / 'InfoNCE.md').write_text('# InfoNCE', encoding='utf-8')
        prepare(self.config)
        apply_preview(self.config)
        run(self.config)
        reference = next(e for e in self.index()['concept_references'] if e['target'] == 'InfoNCE')
        self.assertEqual(reference['status'], 'ambiguous')
        self.assertIsNone(reference['resolved'])

    def test_generated_footer_cannot_supply_evidence_for_its_own_entry(self):
        text = '# Lecture\n\n## 相关词条\n\nSoftmax\n'
        note = parse_note(text.encode(), 'courses/Lecture.md')
        selection = {**self.selection, 'concepts':[self.selection['concepts'][1]]}
        with self.assertRaises(ValueError):
            discover_concepts(selection, {note['path']:note}, [])

    def test_crlf_bom_and_original_bytes_survive_and_repeat_apply_is_idempotent(self):
        original = b'\xef\xbb\xbf# Lecture\r\n\r\nInfoNCE uses softmax.'
        self.note.write_bytes(original)
        prepare(self.config)
        self.assertEqual(self.note.read_bytes(), original)
        apply_preview(self.config)
        after = self.note.read_bytes()
        self.assertTrue(after.startswith(original))
        self.assertNotIn(b'\n', after[len(original):].replace(b'\r\n', b''))
        self.assertEqual((self.task / 'source-before.txt').read_bytes(), original)
        apply_preview(self.config)
        self.assertEqual(self.note.read_bytes(), after)
        with self.assertRaises(ValueError):
            prepare(self.config)

    def test_edit_since_preview_is_preserved_and_stale_preview_rejected(self):
        prepare(self.config)
        original = self.note.read_bytes()
        edited = original + b'\nA human added content.'
        self.note.write_bytes(edited)
        with self.assertRaises(ValueError):
            apply_preview(self.config)
        self.assertEqual(self.note.read_bytes(), edited)
        self.assertEqual((self.task / 'source-before.txt').read_bytes(), original)

    def test_selection_change_recomputes_concepts_without_reparsing_source(self):
        run(self.config)
        self.selection['concepts'] = [self.selection['concepts'][0]]
        self.save_selection()
        result = run(self.config)
        self.assertEqual(result['stats']['parsed'], 0)
        self.assertEqual(list(self.index()['concepts']), ['InfoNCE'])

    def test_entry_body_links_create_concept_relations_and_source_backlinks(self):
        entries = self.vault / 'entries'
        entries.mkdir()
        page = entries / 'InfoNCE.md'
        page.write_text('# InfoNCE\n\nUses [[Softmax]]. Source: [[courses/Lecture]].', encoding='utf-8')
        prepare(self.config)
        apply_preview(self.config)
        first = run(self.config)
        self.assertEqual(first['stats']['concept_pages_parsed'], 1)
        self.assertEqual(first['concept_page_changes']['added'], ['entries/InfoNCE.md'])
        relation = self.index()['concept_relations'][0]
        self.assertEqual((relation['source_concept_id'],relation['concept_id']), ('InfoNCE','Softmax'))
        self.assertEqual(relation['status'], 'pending_concept')
        self.assertEqual(self.index()['backlinks']['courses/Lecture.md'][0]['source'], 'entries/InfoNCE.md')
        self.assertEqual(run(self.config)['stats']['concept_pages_parsed'], 0)
        page.write_text('# InfoNCE\n\nRevised explanation without that concept link.', encoding='utf-8')
        updated = run(self.config)
        self.assertEqual(updated['stats']['parsed'], 0)
        self.assertEqual(updated['stats']['concept_pages_parsed'], 1)
        self.assertEqual(updated['concept_page_changes']['modified'], ['entries/InfoNCE.md'])
        self.assertEqual(self.index()['concept_relations'], [])
        self.assertNotIn('courses/Lecture.md', self.index()['backlinks'])


class ReservedOutput(unittest.TestCase):
    def test_process_writers_refuse_reserved_output_before_any_io(self):
        reserved = Path(__file__).resolve().parents[1] / 'output'
        before = set(reserved.iterdir()) if reserved.exists() else set()
        nonexistent = reserved / uuid.uuid4().hex / 'config.json'
        # No fixture is created here: rejection must precede config reads,
        # locks, backups and temporary output files.
        for operation in (run, prepare, apply_preview):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(ValueError, '用户点名'):
                    operation(nonexistent)
        with self.assertRaisesRegex(ValueError, '用户点名'):
            write_owned(nonexistent, '{}')
        after = set(reserved.iterdir()) if reserved.exists() else set()
        self.assertEqual(after, before)
        self.assertFalse(nonexistent.parent.exists())


if __name__ == '__main__':
    unittest.main()
