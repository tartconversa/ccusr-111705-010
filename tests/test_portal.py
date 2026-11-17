import unittest
from playwright.sync_api import sync_playwright
from test_browser import BrowserBaselineTest
from app.site import DATA
from app.capture import read_detail_entry
from app.records import save_detail_entries, read_detail_entries
from app.review import review_entries
from tempfile import TemporaryDirectory
from pathlib import Path
import sqlite3

class PortalInteractionTest(BrowserBaselineTest):
    def test_attachment_digest_and_category_versions(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + 'detail?id=' + DATA['items'][0]['id'])
                page.locator('#attachment').set_input_files({'name':'draft.txt','mimeType':'text/plain','buffer':b'first'})
                page.locator('#upload-digest').get_by_text('附件摘要：').wait_for()
                first_digest = page.locator('#upload-digest').inner_text()
                page.locator('#draft').click()
                page.locator('#confirm').click()
                self.assertIn('材料摘要已核', page.locator('#draft-check').inner_text())
                page.locator('#attachment').set_input_files({'name':'draft.txt','mimeType':'text/plain','buffer':b'second'})
                page.wait_for_function('(previous) => document.querySelector("#upload-digest").textContent !== previous', arg=first_digest)
                self.assertNotEqual(first_digest, page.locator('#upload-digest').inner_text())
                page.locator('#confirm').click()
                self.assertIn('材料版本待核对', page.locator('#draft-check').inner_text())
                page.reload()
                self.assertIn('草稿已恢复', page.locator('#draft-state').inner_text())
                self.assertEqual(page.locator('#attachment').input_value(), '')
                page.locator('#confirm').click()
                self.assertIn('材料版本待核对', page.locator('#draft-check').inner_text())
                page.locator('#category').select_option('食饮')
                self.assertEqual(page.locator('#upload-digest').inner_text(), '')
            finally:
                browser.close()
    def test_selected_business_state_reaches_receipt(self):
        initial = read_detail_entry(self.origin, DATA['items'][0]['id'])
        changed = read_detail_entry(self.origin, DATA['items'][0]['id'], '食饮')
        self.assertNotEqual(initial['detail_fact']['business_key'], changed['detail_fact']['business_key'])
        with TemporaryDirectory() as directory:
            database = Path(directory) / 'selected.sqlite3'
            save_detail_entries(database, [initial, changed])
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT count(DISTINCT business_key) FROM detail_entries').fetchone()[0], 2)
            review = review_entries(read_detail_entries(database))
            self.assertEqual(len(review), 2)
            self.assertTrue(all(item['submission'] == 'not_performed' for item in review))
    def test_distinct_source_state_transitions(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + 'detail?id=' + DATA['items'][0]['id'], wait_until='domcontentloaded')
                page.locator('#attachment').set_input_files({'name':'draft.txt','mimeType':'text/plain','buffer':b'local'})
                page.locator('#upload-digest').get_by_text('附件摘要：').wait_for()
                self.assertEqual(len(page.locator('#upload-digest').inner_text().split('：')[-1]), 64)
                page.locator('#category').select_option('食饮')
                self.assertEqual(page.locator('#upload-digest').inner_text(), '')
            finally:
                browser.close()
    def test_entry_visit_is_append_only_and_linked(self):
        entry = read_detail_entry(self.origin, DATA['items'][0]['id'])
        self.assertEqual(entry['catalog_fact']['identity'], entry['id'])
        self.assertIn('detail', entry['source'])
        self.assertIn(DATA['items'][0]['id'], entry['detail_fact']['business_key'])
        with TemporaryDirectory() as directory:
            database = Path(directory) / 'visits.sqlite3'
            save_detail_entries(database, [entry, entry])
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM detail_entries').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT count(DISTINCT business_key) FROM detail_entries').fetchone()[0], 1)

    def test_browser_business_interaction(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + "detail?id=" + DATA["items"][0]["id"], wait_until="domcontentloaded")
                page.locator('#attachment').set_input_files({'name':'sample.txt','mimeType':'text/plain','buffer':b'local'});self.assertIn('sample.txt',page.locator('#draft-state').inner_text());page.locator('#draft').click();page.locator('#confirm').click();self.assertIn('待人工确认',page.locator('#confirmation').inner_text());page.locator('#category').select_option('食饮');self.assertEqual(page.locator('#attachment').input_value(),'');page.locator('#confirm').click();self.assertEqual(page.locator('#confirmation').inner_text(),'草稿已变化')
            finally:
                browser.close()
