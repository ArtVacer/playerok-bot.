import os
import requests

response = requests.post(
    'https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/getUpdates',
    json={'timeout': 0, 'allowed_updates': ['message']}, timeout=20)
if response.status_code != 200:
    raise SystemExit('Telegram не вернул обновления. Проверьте токен и отсутствие webhook.')
chats = {item['message']['chat']['id'] for item in response.json().get('result', [])
         if 'message' in item and item['message']['chat']['type'] == 'private'}
print('ID личных чатов:', sorted(chats))
if not chats:
    print('Нажмите Start в боте и повторите команду.')
