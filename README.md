# Playerok subscription monitor

Hourly Telegram reports for configured subscription listings. Schedule: minute 17 of every hour (GitHub may delay runs).

## Setup

In Settings → Secrets and variables → Actions add:

- TELEGRAM_BOT_TOKEN: BotFather token.
- TELEGRAM_CHAT_ID: destination chat ID.
- BOT_CONFIG_JSON: full contents of config.json from the supplied project archive. This contains private purchase costs and target profits. Keep it in Secrets.

Open the Telegram bot and press Start. Then Actions → Hourly subscription prices → Run workflow.

## Status and limitations

Live price retrieval and delivery have not yet been verified. Playerok previously showed DDoS-Guard. The collector reads a single in-stock RUB Product from JSON-LD on each configured listing. Blocked or unsupported pages produce an explicit error. Previously collected prices retain their timestamp and are excluded from fresh recommendations. No anti-bot bypass is implemented.

The sample covers configured listings only, not the whole marketplace. It measures asking prices, not completed sales. Recommended price is the larger of the configured profit floor and lower quartile minus one ruble. Taxes, promotions and refunds are excluded. Withdrawal uses the configured minimum fee and batch size. Confirm equivalence of supplier products and competitor offers before pricing.

GitHub cache stores the last successful snapshot and may be evicted. Public repository schedules may be disabled after 60 days without activity. Tokens and private settings belong in Secrets, never in tracked files.
