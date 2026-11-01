import json
from pathlib import Path
import tempfile
import unittest
from replacement.file_sink import FileSink


def event(invoice='one'):
    return {'invoiceId':invoice,'modifiedDate':'2026-10-01T00:00:10Z','status':'success'}


class FileSinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'lake'
    def test_durable_batch_restores_offset_without_dropping_duplicates(self):
        s=FileSink(self.root,'topic');s.add(0,0,event());s.add(0,1,event());s.flush(0)
        restored=FileSink(self.root,'topic')
        self.assertEqual(restored.offsets[0],2);self.assertEqual(restored.rows(),2)
        restored.add(0,1,event())
        self.assertEqual(restored.rows(),2)
    def test_unflushed_records_are_replayed_after_crash(self):
        s=FileSink(self.root,'topic');s.add(0,0,event())
        restored=FileSink(self.root,'topic')
        self.assertEqual(restored.offsets[0],0)
        restored.add(0,0,event());restored.flush(0)
        self.assertEqual(restored.rows(),1)
    def test_corruption_fails_closed(self):
        s=FileSink(self.root,'topic');s.add(0,0,event());s.flush(0)
        next(self.root.glob('partition=*/batch=*/dt=*/events.jsonl')).write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'Corrupt'):FileSink(self.root,'topic')
    def test_end_marker_is_not_written_as_payment(self):
        s=FileSink(self.root,'topic');s.add(0,0,event());s.add(0,1,{'_control':'end'})
        restored=FileSink(self.root,'topic')
        self.assertEqual(restored.rows(),1);self.assertEqual(restored.offsets[0],2)
        self.assertIn(0,restored.ended)
    def test_offset_gap_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'gap'):FileSink(self.root,'topic').add(0,10,event())
    def test_partial_directory_cannot_advance_checkpoint(self):
        s=FileSink(self.root,'topic');folder=self.root/'partition=0'/'.partial-crash';folder.mkdir()
        (folder/'manifest.json').write_text(json.dumps({'next_offset':100}))
        self.assertEqual(FileSink(self.root,'topic').offsets[0],0)
        self.assertFalse(folder.exists())


if __name__=='__main__':unittest.main()
