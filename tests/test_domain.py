import unittest
from app.domain import interpret_card
from app.site import DATA

class DomainCardTest(unittest.TestCase):
    def test_catalog_fact_keeps_business_condition(self):
        item = DATA['items'][0]
        fact = interpret_card(item)
        self.assertEqual(fact['identity'], item['id'])
        self.assertEqual(fact['condition'], item['choices'][0])
        self.assertEqual(fact['kind'], 'application')

    def test_malformed_card_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            interpret_card({'id':'unknown','summary':'incomplete'})
