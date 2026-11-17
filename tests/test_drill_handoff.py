import json
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from test_browser import BrowserBaselineTest
from app.site import DATA
from app.drill import (
    run_draft_drill,
    require_loopback,
    sha256_hex,
    FIRST_CONTENT,
    SECOND_CONTENT,
    SAME_FILENAME,
    STEP_CATEGORY_SWITCH,
    STEP_VALIDATION_FOCUS,
    STEP_SESSION_BOUNDARY,
    STEP_SUBMISSION_GUARD_PROBE,
)
from app.handoff import build_handoff, write_handoff, CONSISTENT, MISMATCH, BLOCKED
from app import drill_cli


class DraftDrillTest(BrowserBaselineTest):
    def setUp(self):
        self.item_id = DATA['items'][0]['id']
        self.result = run_draft_drill(self.origin, self.item_id)

    def test_full_drill_produces_reviewable_handoff_without_submission(self):
        handoff = build_handoff(self.result)
        self.assertEqual(handoff['record_type'], 'stall_draft_handoff')
        self.assertEqual(handoff['item_id'], self.item_id)
        self.assertEqual(handoff['submission_conclusion'], 'not_performed')
        self.assertEqual(handoff['unexpected_write_attempts'], [])

        evidence = handoff['submission_evidence']
        self.assertTrue(evidence['guard_probe_blocked'])
        self.assertTrue(evidence['still_on_detail_page'])
        self.assertFalse(evidence['success_indicator_present'])
        # 唯一被拦截的写请求是演练自己发起的守卫自检。
        self.assertEqual(len(evidence['mutating_attempts_blocked']), 1)
        self.assertTrue(evidence['mutating_attempts_blocked'][0]['url'].endswith('/submit'))

        verdicts = {row['dimension']: row['verdict'] for row in handoff['consistency']}
        self.assertIn('摊位类别 → 所需材料', verdicts)
        self.assertIn('材料预览（同名文件不同内容）', verdicts)
        self.assertEqual(verdicts['换类别后旧材料是否仍附在申请上'], CONSISTENT)
        self.assertEqual(verdicts['确认页（旧材料不得沿用）'], MISMATCH)
        self.assertEqual(verdicts['校验错误与焦点跳转'], BLOCKED)
        self.assertTrue(all(item['handled'] for item in handoff['anomaly_handling']))

    def test_same_filename_distinct_contents_have_distinct_digests(self):
        expected = self.result['expected_digests'][SAME_FILENAME]
        self.assertEqual(expected['first'], sha256_hex(FIRST_CONTENT))
        self.assertEqual(expected['second'], sha256_hex(SECOND_CONTENT))
        self.assertNotEqual(expected['first'], expected['second'])

        snapshots = {entry['step']: entry['snapshot'] for entry in self.result['steps']
                     if 'snapshot' in entry}
        self.assertTrue(snapshots['same_name_replaced']['uploadDigest'].endswith(expected['second']))
        self.assertTrue(snapshots['first_preview']['uploadDigest'].endswith(expected['first']))

    def test_category_switch_clears_material_and_updates_requirement(self):
        snapshots = {entry['step']: entry['snapshot'] for entry in self.result['steps']
                     if 'snapshot' in entry}
        before = snapshots['first_preview']
        after = snapshots[STEP_CATEGORY_SWITCH]
        self.assertNotEqual(before['requiredMaterial'], after['requiredMaterial'])
        self.assertEqual(after['attachmentInputValue'], '')
        self.assertEqual(after['uploadDigest'], '')
        self.assertEqual(after['storedDraft']['category'], before['category'])

    def test_focus_jump_is_recoverable_with_fresh_locators(self):
        # 直接在浏览器里独立复现一次焦点跳转，验证跳转后重新定位元素可继续流程。
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + 'detail?id=' + self.item_id, wait_until='domcontentloaded')
                page.locator('#confirm').click()
                page.wait_for_function(
                    "() => document.activeElement && document.activeElement.id === 'attachment'"
                )
                self.assertEqual(page.evaluate('document.activeElement.id'), 'attachment')
                self.assertNotEqual(page.locator('#validation-error').inner_text(), '')
                # 跳转后重新获取定位器，而不是复用旧句柄。
                page.locator('#attachment').set_input_files(
                    {'name': 'recover.txt', 'mimeType': 'text/plain', 'buffer': FIRST_CONTENT}
                )
                page.wait_for_function(
                    "() => document.querySelector('#upload-digest').textContent !== ''"
                )
                self.assertEqual(page.locator('#validation-error').inner_text(), '')
            finally:
                browser.close()

    def test_session_storage_boundary_keeps_drafts_local(self):
        snapshots = {entry['step']: entry['snapshot'] for entry in self.result['steps']
                     if 'snapshot' in entry}
        boundary = snapshots[STEP_SESSION_BOUNDARY]
        self.assertIsNone(boundary['storedDraft'])
        self.assertEqual(boundary['draftState'], '')

    def test_double_click_does_not_create_extra_versions_or_requests(self):
        snapshots = {entry['step']: entry['snapshot'] for entry in self.result['steps']
                     if 'snapshot' in entry}
        saved_version = snapshots['draft_saved']['storedDraft']['version']
        confirm_version = snapshots['confirm_consistent']['storedDraft']['version']
        self.assertEqual(saved_version, confirm_version)
        guard_step = next(step for step in self.result['steps']
                          if step['step'] == STEP_SUBMISSION_GUARD_PROBE)
        self.assertTrue(guard_step['probe']['blocked'])

    def test_loopback_guard_rejects_non_local_origins(self):
        for bad in ('https://example.com/', 'http://10.0.0.1/', 'ftp://127.0.0.1/'):
            with self.assertRaises(ValueError):
                require_loopback(bad)
        require_loopback('http://127.0.0.1:8765/')
        require_loopback('http://localhost:8765/')


class HandoffBuilderTest(unittest.TestCase):
    def _snap(self, **overrides):
        base = {
            'url': 'http://127.0.0.1:9/detail?id=stall-01', 'mainKey': 'stall-01',
            'category': '手作', 'requiredMaterial': '所需材料：工艺说明文档（含传承人介绍）',
            'attachmentName': None, 'attachmentInputValue': '', 'uploadDigest': '',
            'draftState': '', 'confirmation': '', 'draftCheck': '', 'validationError': '',
            'activeElementId': None,
            'storedDraft': {'category': '手作', 'filename': None, 'version': 2,
                            'digest': '附件摘要：' + 'a' * 64},
        }
        base.update(overrides)
        return base

    def _trace(self):
        digest_a = '附件摘要：' + 'a' * 64
        digest_b = '附件摘要：' + 'b' * 64
        steps = [
            {'step': 'first_preview', 'label': '', 'snapshot': self._snap(
                attachmentName=SAME_FILENAME, uploadDigest=digest_a,
                draftState='已预览：' + SAME_FILENAME)},
            {'step': 'draft_saved', 'label': '', 'snapshot': self._snap(
                attachmentName=SAME_FILENAME, uploadDigest=digest_a,
                draftState='草稿：手作 / v2')},
            {'step': 'confirm_consistent', 'label': '', 'snapshot': self._snap(
                attachmentName=SAME_FILENAME, uploadDigest=digest_a,
                confirmation='待人工确认 / v2', draftCheck='手作：材料摘要已核')},
            {'step': 'same_name_replaced', 'label': '', 'snapshot': self._snap(
                attachmentName=SAME_FILENAME, uploadDigest=digest_b)},
            {'step': 'confirm_stale_draft', 'label': '', 'snapshot': self._snap(
                attachmentName=SAME_FILENAME, uploadDigest=digest_b,
                confirmation='草稿已变化', draftCheck='材料版本待核对')},
            {'step': 'category_switched', 'label': '', 'snapshot': self._snap(
                category='食饮', requiredMaterial='所需材料：现场制作品安全说明',
                attachmentInputValue='', uploadDigest='', draftState='材料待核对')},
            {'step': 'validation_focus_jump', 'label': '', 'snapshot': self._snap(
                category='食饮', validationError='校验未通过：当前类别缺少已核对材料，焦点已移回材料上传框',
                activeElementId='attachment')},
            {'step': 'recovered_consistent', 'label': '', 'snapshot': self._snap(
                draftCheck='手作：材料摘要已核')},
            {'step': 'leave_and_return', 'label': '', 'snapshot': self._snap(
                draftState='草稿已恢复；材料需重新附上并核对', attachmentInputValue='',
                uploadDigest='')},
            {'step': 'confirm_restored_without_material', 'label': '', 'snapshot': self._snap(
                attachmentInputValue='', validationError='校验未通过：当前类别缺少已核对材料，焦点已移回材料上传框',
                activeElementId='attachment')},
            {'step': 'restored_reattach', 'label': '', 'snapshot': self._snap(
                attachmentName=SAME_FILENAME, uploadDigest=digest_a,
                draftCheck='手作：材料摘要已核')},
            {'step': 'reload_restore', 'label': '', 'snapshot': self._snap(
                draftState='草稿已恢复；材料需重新附上并核对')},
            {'step': 'new_session_no_restore', 'label': '', 'snapshot': self._snap(
                draftState='', storedDraft=None)},
        ]
        return {
            'origin': 'http://127.0.0.1:9/', 'item_id': 'stall-01',
            'draft_key': 'stall-draft:stall-01',
            'started_at': 't0', 'finished_at': 't1',
            'expected_digests': {SAME_FILENAME: {'first': 'a' * 64, 'second': 'b' * 64}},
            'submission_evidence': {
                'conclusion': 'not_performed', 'mutating_attempts_blocked': [],
                'final_url': 'http://127.0.0.1:9/detail?id=stall-01',
                'still_on_detail_page': True, 'success_indicator_present': False,
                'guard_probe_blocked': True,
            },
            'steps': steps,
        }

    def test_clean_synthetic_trace_is_not_performed(self):
        handoff = build_handoff(self._trace())
        self.assertEqual(handoff['submission_conclusion'], 'not_performed')
        self.assertEqual(handoff['unexpected_write_attempts'], [])
        verdicts = {row['dimension']: row['verdict'] for row in handoff['consistency']}
        self.assertEqual(verdicts['确认页（旧材料不得沿用）'], MISMATCH)
        self.assertEqual(verdicts['校验错误与焦点跳转'], BLOCKED)

    def test_unexpected_write_attempt_forces_manual_review(self):
        trace = self._trace()
        trace['submission_evidence']['mutating_attempts_blocked'] = [
            {'method': 'POST', 'url': 'http://127.0.0.1:9/apply'}
        ]
        handoff = build_handoff(trace)
        self.assertEqual(handoff['submission_conclusion'], 'needs_manual_review')
        self.assertEqual(len(handoff['unexpected_write_attempts']), 1)

    def test_guard_probe_alone_does_not_taint_conclusion(self):
        trace = self._trace()
        trace['submission_evidence']['mutating_attempts_blocked'] = [
            {'method': 'POST', 'url': 'http://127.0.0.1:9/submit'}
        ]
        self.assertEqual(build_handoff(trace)['submission_conclusion'], 'not_performed')

    def test_success_indicator_forces_manual_review(self):
        trace = self._trace()
        trace['submission_evidence']['success_indicator_present'] = True
        self.assertEqual(build_handoff(trace)['submission_conclusion'], 'needs_manual_review')

    def test_write_handoff_emits_json_and_markdown(self):
        # 用一次真实演练验证落盘结构。
        from app.site import start_server
        import threading
        server = start_server()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            origin = f'http://127.0.0.1:{server.server_port}/'
            result = run_draft_drill(origin, DATA['items'][0]['id'])
            with tempfile.TemporaryDirectory() as directory:
                paths = write_handoff(Path(directory), result)
                self.assertTrue(paths['json'].exists() and paths['markdown'].exists())
                payload = json.loads(paths['json'].read_text(encoding='utf-8'))
                self.assertEqual(payload['handoff']['submission_conclusion'], 'not_performed')
                self.assertEqual(payload['trace']['item_id'], result['item_id'])
                markdown = paths['markdown'].read_text(encoding='utf-8')
                self.assertIn('人工复核', markdown)
                self.assertIn('not_performed', markdown)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


class DrillCliTest(unittest.TestCase):
    def test_cli_runs_ephemeral_server_and_writes_records(self):
        with tempfile.TemporaryDirectory() as directory:
            written = drill_cli.main([DATA['items'][0]['id'], '-o', directory])
            self.assertEqual(len(written), 1)
            files = list(Path(directory).iterdir())
            self.assertEqual(len(files), 2)
            self.assertTrue(any(path.suffix == '.md' for path in files))
            self.assertTrue(any(path.suffix == '.json' for path in files))

    def test_cli_rejects_unknown_identity(self):
        with self.assertRaises(SystemExit):
            drill_cli.main(['not-a-stall', '-o', tempfile.gettempdir()])


if __name__ == '__main__':
    unittest.main()
