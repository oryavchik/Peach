import tempfile
import unittest
from pathlib import Path
from window_store import WindowStore


def event(t, invoice='one', status='failure'):
    return {'invoiceId':invoice,'modifiedDate':t,'receivedAt':t,'status':status,'paymentMethod':'card'}


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'state.db'
    def tearDown(self):
        self.tmp.cleanup()
    def store(self, lateness=120):
        store=WindowStore(self.path,'group','payments',partitions=1,lateness=lateness)
        self.addCleanup(store.close)
        return store
    def test_exact_duplicates_and_replay_are_idempotent(self):
        s=self.store(); e=event('2026-10-01T00:00:10Z')
        s.process(0,0,e);s.process(0,1,e);s.process(0,1,e)
        self.assertEqual(s.summary()['accepted'],1)
        self.assertEqual(s.summary()['duplicates'],1)
    def test_restart_restores_window_and_checkpoint(self):
        s=self.store();s.process(0,0,event('2026-10-01T00:00:10Z'));s.db.close()
        s=self.store();self.assertEqual(s.offset(0),1)
        results=s.process(0,1,{'_control':'end'})
        self.assertEqual(results[0]['failure_rate'],1)
        self.assertTrue(results[0]['alert'])
    def test_watermark_boundary_and_late_rejection(self):
        s=self.store(0);s.process(0,0,event('2026-10-01T00:01:00Z','new'))
        s.process(0,1,event('2026-10-01T00:00:59Z','late'))
        self.assertEqual(s.summary()['late_rejected'],1)
    def test_two_minutes_admits_same_event(self):
        s=self.store(120);s.process(0,0,event('2026-10-01T00:01:00Z','new'))
        s.process(0,1,event('2026-10-01T00:00:59Z','late'))
        self.assertEqual(s.summary()['accepted'],2)
    def test_strictly_above_ten_percent(self):
        s=self.store()
        for i in range(10):s.process(0,i,event('2026-10-01T00:00:10Z',str(i),'failure' if i==0 else 'success'))
        self.assertFalse(s.process(0,10,{'_control':'end'})[0]['alert'])
    def test_offset_gap_is_not_silently_accepted(self):
        s=self.store()
        with self.assertRaises(ValueError):s.process(0,1,event('2026-10-01T00:00:10Z'))
        self.assertEqual(s.summary().get('events',0),0)


if __name__=='__main__':unittest.main()
