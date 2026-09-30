"""Local, rebuild-independent source review metrics in the backup database."""
from datetime import datetime, timedelta

KINDS = ('received', 'opened', 'highlighted', 'saved', 'quoted', 'dismissed', 'evaluated', 'matched')


class Forest:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS forest_events (source TEXT, link TEXT, kind TEXT, month TEXT, PRIMARY KEY(source,link,kind,month))')
            db.execute('CREATE TABLE IF NOT EXISTS forest_received (source TEXT, link TEXT, PRIMARY KEY(source,link))')
            db.execute('CREATE TABLE IF NOT EXISTS forest_reviews (source TEXT PRIMARY KEY, until TEXT, decision TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS forest_meta (started TEXT)')
            if not db.execute('SELECT 1 FROM forest_meta').fetchone():
                db.execute('INSERT INTO forest_meta VALUES (?)', (datetime.now().isoformat(timespec='seconds'),))

    def record(self, article, kind, now=None):
        source, link = article.get('source_url'), article.get('link')
        if not source or not link or kind not in KINDS:
            return
        month = (now or datetime.now()).strftime('%Y-%m')
        with self.store.connect() as db:
            if kind == 'received':
                cursor = db.execute('INSERT OR IGNORE INTO forest_received VALUES (?,?)', (source, link))
                if not cursor.rowcount:
                    return
            db.execute('INSERT OR IGNORE INTO forest_events VALUES (?,?,?,?)', (source, link, kind, month))

    def review(self, source, decision):
        if decision not in ('keep', 'later', 'reset'):
            raise ValueError('Acción desconocida')
        with self.store.connect() as db:
            if decision == 'reset':
                db.execute('DELETE FROM forest_reviews WHERE source=?', (source,))
            else:
                until = (datetime.now() + timedelta(days=30)).isoformat(timespec='seconds')
                db.execute('INSERT OR REPLACE INTO forest_reviews VALUES (?,?,?)', (source, until, decision))

    def report(self, categories, month='', sort='review'):
        with self.store.connect() as db:
            counts = db.execute('SELECT source,kind,COUNT(DISTINCT link) FROM forest_events '
                                + ('WHERE month=? ' if month else '') + 'GROUP BY source,kind', (month,) if month else ()).fetchall()
            reviews = {s: (u, d) for s, u, d in db.execute('SELECT * FROM forest_reviews')}
            months = [r[0] for r in db.execute('SELECT DISTINCT month FROM forest_events ORDER BY month DESC')]
            started = db.execute('SELECT started FROM forest_meta').fetchone()[0]
        metrics = {}
        for source, kind, count in counts:
            metrics.setdefault(source, {})[kind] = count
        rows, seen = [], set()
        today = datetime.now().isoformat(timespec='seconds')
        for category in categories:
            for source in category['sitios']:
                url = source['url']
                if url in seen or source.get('source_type') == 'shortcut':
                    continue
                seen.add(url)
                row = dict.fromkeys(KINDS, 0)
                row.update(metrics.get(url, {}))
                until, decision = reviews.get(url, ('', ''))
                pending = until <= today
                reasons = []
                if row['received'] == 0: reasons.append('Sin artículos nuevos observados')
                if row['received'] and not row['opened']: reasons.append('Sin aperturas registradas')
                if row['evaluated'] and not row['matched']: reasons.append('Sin coincidencias con Radar')
                if row['dismissed']: reasons.append('Artículos marcados No me interesa')
                row.update(url=url, name=source.get('nombre', url), pending=pending,
                           review=('Pendiente de revisión' if pending else ('Conservada hasta ' if decision == 'keep' else 'Pospuesta hasta ') + until[:10]),
                           reason=' · '.join(reasons) or 'Sin señales de desinterés registradas',
                           radar=(str(round(100 * row['matched'] / row['evaluated'])) + '%' if row['evaluated'] else 'Sin evaluar'))
                rows.append(row)
        if sort in KINDS:
            rows.sort(key=lambda r: (-r[sort], r['name'].casefold()))
        elif sort == 'irrelevant':
            rows.sort(key=lambda r: (not bool(r['evaluated']), r['matched'] / max(1, r['evaluated']), r['name'].casefold()))
        elif sort == 'unopened':
            rows.sort(key=lambda r: (r['opened'], r['name'].casefold()))
        elif sort == 'quiet':
            rows.sort(key=lambda r: (r['received'], r['name'].casefold()))
        else:
            rows.sort(key=lambda r: (not r['pending'], r['opened'] + r['saved'] + r['highlighted'] + r['quoted'], -r['dismissed'], r['name'].casefold()))
        return dict(rows=rows, months=months, started=started[:10], pending=sum(r['pending'] for r in rows))
