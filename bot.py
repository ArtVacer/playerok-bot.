"""Hourly price report, delivered to one configured Telegram chat."""
import json
import math
import os
import statistics
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent


def profit(price, cost, fee, withdrawal, minimum, batch):
    balance = Decimal(str(price)) * (1 - Decimal(str(fee)))
    charge = max(balance * Decimal(str(withdrawal)), Decimal(str(minimum)) / batch)
    return balance - charge - Decimal(str(cost))


def floor_price(cost, target, fee, withdrawal, minimum, batch):
    required = Decimal(str(cost)) + Decimal(str(target))
    sale = 1 - Decimal(str(fee))
    withdrawal = Decimal(str(withdrawal))
    return math.ceil(max(required / (sale * (1 - withdrawal)),
                         (required + Decimal(str(minimum)) / batch) / sale))


def product_price(html):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True).lower() if soup.title else ''
    if any(word in title for word in ('ddos-guard', 'just a moment', 'access denied')):
        raise ValueError('Защита сайта блокирует доступ')
    # Only the primary Product structured data. Related-product cards are ignored.
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict):
                nodes_graph = node.get('@graph', [node])
                products.extend(n for n in nodes_graph if isinstance(n, dict)
                                and n.get('@type') == 'Product')
    if len(products) != 1:
        raise ValueError('Не удалось однозначно прочитать карточку товара')
    offers = products[0].get('offers', {})
    offers = offers if isinstance(offers, list) else [offers]
    prices = []
    for offer in offers:
        if offer.get('priceCurrency') != 'RUB':
            continue
        if offer.get('availability', '').split('/')[-1] != 'InStock':
            continue
        try:
            price = Decimal(str(offer['price']))
            if price.is_finite() and price > 0:
                prices.append(price)
        except (KeyError, ValueError, ArithmeticError):
            continue
    if len(prices) != 1:
        raise ValueError('Нет однозначной цены доступного товара в рублях')
    return float(prices[0])


def fetch_price(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'playerok.com' or not parsed.path.startswith('/products/'):
        raise ValueError('Разрешены только HTTPS-карточки Playerok')
    response = requests.get(url, timeout=25, allow_redirects=False)
    if response.status_code != 200:
        raise ValueError(f'Сайт вернул HTTP {response.status_code}')
    return product_price(response.text)


def report(config, state, fetch=fetch_price):
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    lines = ['Подписки • проверка ' + now, 'Цены по отслеживаемым лотам, ₽.']
    for product in config['products']:
        current = []
        failures = []
        for url in dict.fromkeys(product['urls']):
            try:
                current.append({'url': url, 'price': fetch(url)})
            except (requests.RequestException, ValueError) as error:
                failures.append(str(error))
        old = state.get(product['id'], {})
        cost = product['purchase'] + config['extra']
        lines.extend(['', product['name'], f'Закупка + расходы: {cost} ₽'])
        if current:
            prices = sorted(row['price'] for row in current)
            median = statistics.median(prices)
            lines.append(f'Мин {min(prices):g} · медиана {median:g} · макс {max(prices):g}')
            lines.append(f'Проверено лотов: {len(prices)}/{len(set(product["urls"]))}')
            if old.get('offers'):
                previous = statistics.median(row['price'] for row in old['offers'])
                lines.append(f'Изменение медианы: {median - previous:+g} ₽ (состав лотов может меняться)')
            for fee in config['fees']:
                args = (fee, config['withdrawal'], config['withdrawal_minimum'], config['withdrawal_batch'])
                floor = floor_price(cost, 0, *args)
                target = floor_price(cost, product['target_profit'], *args)
                # Lower quartile balances entry pricing against one cheap outlier.
                lower_quartile = prices[(len(prices) - 1) // 4]
                recommended = max(target, math.ceil(lower_quartile) - 1)
                net = profit(recommended, cost, *args)
                lines.append(f'Комиссия {fee:.0%}: вход {recommended} ₽; остаток {net:.0f} ₽; в ноль {floor} ₽')
                if recommended > median:
                    lines.append('Расчётная цена выше медианы конкурентов.')
            lines.append('Минимальный лот: ' + min(current, key=lambda r: r['price'])['url'])
            state[product['id']] = {'at': now, 'offers': current}
        else:
            lines.append('Свежих цен нет. Рекомендация недоступна.')
            if old.get('offers'):
                prices = [row['price'] for row in old['offers']]
                lines.append(f'Последние данные {old["at"]}: {min(prices):g}–{max(prices):g} ₽')
        if failures:
            lines.append('Ошибки: ' + '; '.join(sorted(set(failures))))
    lines.append('\nРасчёт до налогов, рекламы и возвратов. Цена — ориентир по выборке, объём продаж недоступен.')
    return '\n'.join(lines)


def send(text):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat = os.environ['TELEGRAM_CHAT_ID']
    # Split on line boundaries to respect Telegram's message length limit.
    chunks, chunk = [], ''
    for line in text.splitlines():
        if len(chunk) + len(line) > 3500:
            chunks.append(chunk)
            chunk = ''
        chunk += line + '\n'
    chunks.append(chunk)
    for chunk in chunks:
        response = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                                 json={'chat_id': chat, 'text': chunk, 'link_preview_options': {'is_disabled': True}},
                                 timeout=30)
        if response.status_code != 200 or not response.json().get('ok'):
            # Never log the request URL, which contains the token.
            raise RuntimeError(f'Telegram: отправка не удалась, HTTP {response.status_code}')


def main():
    raw_config = os.environ.get('BOT_CONFIG_JSON')
    if not raw_config:
        raise RuntimeError('Добавьте секрет BOT_CONFIG_JSON в GitHub Actions')
    config = json.loads(raw_config)
    path = ROOT / 'state.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    started_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    text = report(config, state)
    fresh = [item for item in state.values() if item.get('at', '') >= started_at]
    print(f'Fresh products: {len(fresh)}/{len(config["products"])}; fresh offers: {sum(len(item["offers"]) for item in fresh)}', flush=True)
    send(text)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    temporary.replace(path)


if __name__ == '__main__':
    main()
