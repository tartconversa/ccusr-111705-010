import json
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from app.site import DATA, start_server
from app.capture import read_catalog
from app.records import save_catalog

class BrowserBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = start_server()
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}/'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=2)

    def test_browser_collects_real_catalog_and_detail_navigation(self):
        catalog = read_catalog(self.origin)
        self.assertEqual({row['id'] for row in catalog}, {row['id'] for row in DATA['items']})
        self.assertTrue(all(row['source'] == self.origin for row in catalog))
        for item in catalog:
            with urlopen(self.origin + item['href'].lstrip('/')) as response:
                self.assertIn(item['name'], response.read().decode('utf-8'))

    def test_source_is_restricted_to_local_portal(self):
        with self.assertRaises(ValueError):
            read_catalog('https://example.com/')

    def test_catalog_receipt_replaces_only_same_identity(self):
        import tempfile
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'catalog.sqlite3'
            items = read_catalog(self.origin)
            self.assertEqual(save_catalog(database, items), len(items))
            save_catalog(database, items)
            with sqlite3.connect(database) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM catalog').fetchone()[0], len(items))

if __name__ == '__main__': unittest.main()
