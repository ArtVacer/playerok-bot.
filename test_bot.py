import unittest
from bot import product_price, profit, floor_price, report

class Tests(unittest.TestCase):
    def test_price(self):
        html = '<script type="application/ld+json">{"@type":"Product","offers":{"price":"1999","priceCurrency":"RUB","availability":"https://schema.org/InStock"}}</script>'
        self.assertEqual(product_price(html), 1999)
        with self.assertRaises(ValueError):
            product_price('<title>DDoS-Guard</title>')
        with self.assertRaises(ValueError):
            product_price(html.replace('InStock', 'OutOfStock'))

    def test_floor(self):
        for cost in (83, 190, 1403, 7864, 14465, 1659):
            for fee in (.1, .2):
                for batch in (1, 10):
                    args = (fee, .06, 60, batch)
                    floor = floor_price(cost, 200, *args)
                    self.assertGreaterEqual(profit(floor, cost, *args), 200)
                    self.assertLess(profit(floor - 1, cost, *args), 200)

    def test_stale(self):
        config = {
            'extra': 25, 'fees': [.1, .2], 'withdrawal': .06,
            'withdrawal_minimum': 60, 'withdrawal_batch': 1,
            'products': [{'id': 'test', 'name': 'Test', 'purchase': 100,
                          'target_profit': 50,
                          'urls': ['https://playerok.com/products/test']}]
        }
        state = {}
        report(config, state, lambda url: 1999)
        def blocked(url):
            raise ValueError('Заблокировано')
        text = report(config, state, blocked)
        self.assertIn('Свежих цен нет', text)
        self.assertIn('Последние данные', text)
        self.assertNotIn('вход ', text)

if __name__ == '__main__':
    unittest.main()
