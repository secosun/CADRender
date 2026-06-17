import sqlite3, json, uuid, sys

db_path = sys.argv[1] if len(sys.argv) > 1 else '/app/data/blenderserver.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

plans = [
    ('免费体验', 'free', 0, 0, None, None,
     {'concurrency': 1, 'max_resolution': 2048, 'max_samples': 256, 'max_tasks_per_month': 10},
     '', 0, 0),
    ('基础套餐', 'starter', 500000, 5000000, 'dev_price_starter_monthly', 'dev_price_starter_yearly',
     {'concurrency': 3, 'max_resolution': 4096, 'max_samples': 512, 'max_tasks_per_month': 200},
     '每月 200 张渲染，适合小型门窗厂', 1, 1),
    ('专业套餐', 'pro', 980000, 9800000, 'dev_price_pro_monthly', 'dev_price_pro_yearly',
     {'concurrency': 5, 'max_resolution': 8192, 'max_samples': 1024, 'max_tasks_per_month': 500},
     '每月 500 张渲染，适合中型门窗厂', 2, 1),
    ('按次计费', 'payg', 9900, 0, 'dev_price_payg_monthly', None,
     {'concurrency': 2, 'max_resolution': 4096, 'max_samples': 512, 'max_tasks_per_month': 100},
     '按渲染次数付费，用多少付多少', 3, 1),
]

c.execute('DELETE FROM subscription_plans')
for name, slug, monthly, yearly, m_id, y_id, features, desc, sort_order, is_pub in plans:
    c.execute('''INSERT INTO subscription_plans
        (id, name, slug, description, price_monthly_cents, price_yearly_cents,
         stripe_monthly_price_id, stripe_yearly_price_id, features_json,
         is_public, sort_order, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime())''',
        (slug, name, slug, desc, monthly, yearly, m_id, y_id,
         json.dumps(features, ensure_ascii=False), is_pub, sort_order))

conn.commit()
rows = c.execute('SELECT slug, name, price_monthly_cents, stripe_monthly_price_id FROM subscription_plans ORDER BY sort_order').fetchall()
for r in rows:
    print(f'{r[1]:8s}  {r[0]:8s}  ¥{r[2]/100:>6.0f}/月  price_id={r[3]}')
conn.close()
