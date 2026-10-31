"""Durable local event-time state shared by consumers in ONE Kafka group.

SQLite is a local teaching substitute for distributed Flink/Redis state. Every
record and its next-offset checkpoint commit in one transaction. Kafka commits
happen afterward; replay after a crash cannot count a committed record twice.
"""
import json
import sqlite3
import time
from events import fingerprint, iso, timestamp


class WindowStore:
    def __init__(self, path, group, topic, partitions=3, lateness=120):
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        # Two workers may open a brand-new database at the same instant.
        for attempt in range(50):
            try:
                self.db.execute('PRAGMA journal_mode=WAL')
                break
            except sqlite3.OperationalError as error:
                if 'locked' not in str(error) or attempt == 49:
                    raise
                time.sleep(.1)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS progress (partition_id INTEGER PRIMARY KEY,
          next_offset INTEGER NOT NULL DEFAULT 0, max_time INTEGER, ended INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS seen (hash TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS windows (start INTEGER, method TEXT, events INTEGER DEFAULT 0,
          success INTEGER DEFAULT 0, failure INTEGER DEFAULT 0, closed INTEGER DEFAULT 0,
          PRIMARY KEY(start,method));
        CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, count INTEGER DEFAULT 0);
        ''')
        self.lateness = lateness
        with self.db:
            for key, value in {'group': group, 'topic': topic, 'partitions': str(partitions),
                               'lateness': str(lateness)}.items():
                old = self.db.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
                if old and old[0] != value:
                    raise ValueError('State file belongs to different configuration: ' + key)
                self.db.execute('INSERT OR IGNORE INTO config VALUES (?,?)', (key, value))
            for p in range(partitions):
                self.db.execute('INSERT OR IGNORE INTO progress(partition_id) VALUES (?)', (p,))

    def count(self, name):
        self.db.execute('INSERT INTO counters VALUES (?,1) ON CONFLICT(name) DO UPDATE SET count=count+1', (name,))

    def offset(self, partition):
        return self.db.execute('SELECT next_offset FROM progress WHERE partition_id=?', (partition,)).fetchone()[0]

    def watermark(self):
        rows = self.db.execute('SELECT max_time, ended FROM progress').fetchall()
        active = [t for t, ended in rows if not ended]
        if any(t is None for t in active):
            return float('-inf')
        return min(active) - self.lateness if active else float('inf')

    def process(self, partition, offset, event):
        self.db.execute('BEGIN IMMEDIATE')
        results = []
        try:
            if offset < self.offset(partition):
                self.db.execute('COMMIT')
                return []
            if offset != self.offset(partition):
                raise ValueError('Offset gap: refusing to silently lose records')
            self.count('records')
            if event.get('_control') == 'end':
                self.db.execute('UPDATE progress SET ended=1 WHERE partition_id=?', (partition,))
            else:
                self.count('events')
                if self.db.execute('INSERT OR IGNORE INTO seen VALUES (?)', (fingerprint(event),)).rowcount == 0:
                    self.count('duplicates')
                else:
                    t = timestamp(event['modifiedDate'])
                    start = t // 60 * 60
                    # Late is relative to watermark BEFORE this record advances it.
                    if start + 60 <= self.watermark():
                        self.count('late_rejected')
                    else:
                        self.count('accepted')
                        self.db.execute('''INSERT INTO windows(start,method,events,success,failure)
                          VALUES (?,?,1,?,?) ON CONFLICT(start,method) DO UPDATE SET
                          events=events+1,success=success+excluded.success,failure=failure+excluded.failure''',
                          (start, event['paymentMethod'], int(event['status']=='success'), int(event['status']=='failure')))
                    self.db.execute('UPDATE progress SET max_time=MAX(COALESCE(max_time,?),?) WHERE partition_id=?',
                                    (t, t, partition))
            self.db.execute('UPDATE progress SET next_offset=? WHERE partition_id=?', (offset+1, partition))
            wm = self.watermark()
            for start, method, total, success, failure in self.db.execute(
                    'SELECT start,method,events,success,failure FROM windows WHERE closed=0 AND start+60<=? ORDER BY start,method', (wm,)).fetchall():
                terminal = success + failure
                rate = failure / terminal if terminal else 0
                results.append({'type': 'window', 'start': iso(start), 'end': iso(start+60),
                                'method': method, 'events': total, 'terminal': terminal,
                                'failures': failure, 'failure_rate': rate,
                                'all_event_failure_rate': failure/total, 'alert': rate > .10})
                self.db.execute('UPDATE windows SET closed=1 WHERE start=? AND method=?', (start, method))
                if rate > .10:
                    self.count('alerts')
            self.db.execute('COMMIT')
            return results
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def summary(self):
        counts = dict(self.db.execute('SELECT name,count FROM counters'))
        counts.update({'type': 'summary', 'windows': self.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],
                       'closed_windows': self.db.execute('SELECT COUNT(*) FROM windows WHERE closed=1').fetchone()[0],
                       'ended_partitions': self.db.execute('SELECT SUM(ended) FROM progress').fetchone()[0]})
        return counts

    def close(self):
        self.db.close()
