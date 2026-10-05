"""Behavioral checks for false links, incremental relations and source protection."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analyze import GENERATOR, resolve_link, run
from markdown_notes import parse_note


class MarkdownBehavior(unittest.TestCase):
    def test_code_html_math_and_existing_links_do_not_become_mentions(self):
        text = '''# A
正文 [[B|显示名]] 与 ![[image.png]]。
`[[inline-code]]` 和 $HiddenMath$。
[Known](B.md) 与 [ref][x]
<!-- [[comment]] -->

```python
array = [[1, 2], [3, 4]]
"[[fenced-code]]"
```

    [[indented-code]]

[x]: https://example.com
'''
        note = parse_note(text.encode(), 'A.md')
        self.assertEqual([link['target'] for link in note['links']], ['B', 'image.png', 'B.md', 'https://example.com'])
        plain = ''.join(segment['text'] for segment in note['segments'])
        for unwanted in ['inline-code', 'fenced-code', 'indented-code', 'comment', 'HiddenMath', 'Known']:
            self.assertNotIn(unwanted, plain)

    def test_formula_before_rule_does_not_create_a_false_heading(self):
        note = parse_note(b'# Intro\n\n$$\nx=y\n$$\n\n---\n\n## Real heading\n\nText.\n', 'A.md')
        self.assertEqual([heading['text'] for heading in note['headings']], ['Intro', 'Real heading'])

    def test_display_math_interrupts_a_paragraph_without_an_empty_line(self):
        note = parse_note('## 实际标题\n\n一般形式：\n$$\na\n=\nb\n-\nc\n$$\n\n正文。\n'.encode(), 'A.md')
        self.assertEqual([heading['text'] for heading in note['headings']], ['实际标题'])
        plain = ''.join(segment['text'] for segment in note['segments'])
        self.assertIn('一般形式', plain)
        self.assertNotIn('a', plain)

    def test_yaml_is_optional_and_does_not_offset_original_lines(self):
        note = parse_note('---\naliases: [人工智能, AI]\ntags: [learning]\n---\n# Heading\n\n正文 #topic\n'.encode(), 'A.md')
        self.assertEqual(note['aliases'], ['人工智能', 'AI'])
        self.assertEqual(note['headings'][0]['line'], 5)
        self.assertIn('topic', note['tags'])
        malformed = parse_note(b'---\naliases: [\n---\n# Keep reading\n', 'A.md')
        self.assertTrue(malformed['warnings'])
        self.assertEqual(malformed['headings'][0]['text'], 'Keep reading')

    def test_aliases_are_not_silently_used_as_wiki_destinations(self):
        with tempfile.TemporaryDirectory() as temp:
            note = parse_note(b'---\naliases: [AI]\n---\n# Artificial intelligence\n', 'Artificial Intelligence.md')
            edge = resolve_link({'target':'AI','kind':'wiki'}, 'A.md', ['A.md', note['path']], {note['path']:note}, Path(temp))
            self.assertEqual(edge['status'], 'unresolved_in_scope')

    def test_duplicate_names_need_disambiguation_but_local_name_resolves(self):
        with tempfile.TemporaryDirectory() as temp:
            files = ['one/B.md','two/B.md','else/A.md','one/A.md']
            link = {'target':'B','kind':'wiki'}
            self.assertEqual(resolve_link(link, 'else/A.md', files, {}, Path(temp))['status'], 'ambiguous')
            self.assertEqual(resolve_link(link, 'one/A.md', files, {}, Path(temp))['resolved'], 'one/B.md')

    def test_numbered_note_titles_can_omit_the_markdown_extension(self):
        with tempfile.TemporaryDirectory() as temp:
            title = 'course/1.3 logit 概率 交叉熵.md'
            edge = resolve_link({'target':title[:-3],'kind':'wiki'}, 'Report.md', [title], {}, Path(temp))
            self.assertEqual(edge['resolved'], title)


class IncrementalBehavior(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp.name)
        self.source = self.vault / 'notes'
        self.task = self.vault / 'tools' / 'tasks' / 'trial'
        self.source.mkdir()
        self.task.mkdir(parents=True)
        self.config = self.task / 'config.json'
        self.config.write_text(json.dumps({'vault':'../../../','source':'notes','max_suggestions':3}), encoding='utf-8')
        (self.source / 'A.md').write_text('# Source\n\n[[Target]]\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def index(self):
        return json.loads((self.task / 'index.json').read_text(encoding='utf-8'))

    def test_new_note_resolves_old_link_without_reparsing_source(self):
        first = run(self.config)
        self.assertEqual(first['stats']['parsed'], 1)
        self.assertEqual(self.index()['links'][0]['status'], 'unresolved_in_scope')
        unchanged = run(self.config)
        self.assertEqual(unchanged['stats']['parsed'], 0)
        self.assertEqual(unchanged['stats']['reused'], 1)
        (self.source / 'Target.md').write_text('# Target\n', encoding='utf-8')
        changed = run(self.config)
        self.assertEqual(changed['stats']['parsed'], 1)
        self.assertEqual(changed['stats']['reused'], 1)
        self.assertEqual(self.index()['links'][0]['resolved'], 'notes/Target.md')
        self.assertEqual(self.index()['backlinks']['notes/Target.md'][0]['source'], 'notes/A.md')
        (self.source / 'Target.md').rename(self.source / 'Renamed.md')
        moved = run(self.config)
        self.assertEqual(moved['changes']['removed_from_scope'], ['notes/Target.md'])
        self.assertEqual(self.index()['links'][0]['status'], 'unresolved_in_scope')
        self.assertNotIn('notes/Target.md', self.index()['backlinks'])
        incremental = self.index()
        run(self.config, force=True)
        self.assertEqual(incremental, self.index())

    def test_source_content_is_unchanged_and_foreign_output_is_protected(self):
        before = (self.source / 'A.md').read_bytes()
        run(self.config)
        self.assertEqual(before, (self.source / 'A.md').read_bytes())
        (self.task / '检查报告.md').write_text('My personal draft', encoding='utf-8')
        with self.assertRaises(ValueError):
            run(self.config)
        self.assertEqual((self.task / '检查报告.md').read_text(), 'My personal draft')
        self.assertEqual(before, (self.source / 'A.md').read_bytes())
        self.assertFalse((self.task / '.analysis.lock').exists())

    def test_output_cannot_be_inside_the_source(self):
        self.config.write_text(json.dumps({'vault':'../../../','source':'.'}), encoding='utf-8')
        with self.assertRaises(ValueError):
            run(self.config)
        self.assertFalse((self.task / 'index.json').exists())

    def test_external_local_path_does_not_escape_vault(self):
        edge = resolve_link({'kind':'markdown','target':'../../../outside.md'}, 'notes/A.md', [], {}, self.vault)
        self.assertEqual(edge['status'], 'outside_vault')

    def test_existing_lock_prevents_a_second_run(self):
        (self.task / '.analysis.lock').write_text('another process', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            run(self.config)
        self.assertEqual((self.task / '.analysis.lock').read_text(), 'another process')
        self.assertFalse((self.task / 'index.json').exists())


if __name__ == '__main__':
    unittest.main()
