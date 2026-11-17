import unittest
from playwright.sync_api import sync_playwright
from test_browser import BrowserBaselineTest
from app.site import DATA

class PortalInteractionTest(BrowserBaselineTest):
    def test_browser_business_interaction(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(self.origin + "detail?id=" + DATA["items"][0]["id"], wait_until="domcontentloaded")
                page.locator('#attachment').set_input_files({'name':'sample.txt','mimeType':'text/plain','buffer':b'local'});self.assertIn('sample.txt',page.locator('#draft-state').inner_text());page.locator('#draft').click();page.locator('#confirm').click();self.assertIn('待人工确认',page.locator('#confirmation').inner_text());page.locator('#category').select_option('食饮');self.assertEqual(page.locator('#attachment').input_value(),'');page.locator('#confirm').click();self.assertEqual(page.locator('#confirmation').inner_text(),'草稿已变化')
            finally:
                browser.close()
