import io,json,stat,tarfile,tempfile,unittest,zipfile,wave,shutil
from pathlib import Path
import new_scan as ns
from finalize_scan import finalize

def zipped(entries):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
  for n,v in entries:z.writestr(n,v)
 return b.getvalue()

class Safety(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.scanner=ns.Scanner(self.root/'out')
 def tearDown(self):self.tmp.cleanup()
 def rows(self):return [json.loads(x) for x in self.scanner.records.read_text().splitlines()]
 def test_path_and_zip_link(self):
  link=zipfile.ZipInfo('link');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
  self.scanner.record('x','a.zip',zipped([('../escape.py','x'),('/abs','x'),('C:\\evil','x'),(link,'target')]))
  rejects=[r['rejection'] for r in self.rows() if 'rejection'in r]
  self.assertEqual(rejects,['UNSAFE_PATH','UNSAFE_PATH','UNSAFE_PATH','LINK']);self.assertFalse((self.root/'escape.py').exists())
 def test_tar_links(self):
  b=io.BytesIO()
  with tarfile.open(fileobj=b,mode='w') as t:
   m=tarfile.TarInfo('link');m.type=tarfile.SYMTYPE;m.linkname='/tmp/evil';t.addfile(m)
  self.scanner.record('x','a.tar',b.getvalue());self.assertIn('LINK',[r.get('rejection') for r in self.rows()])
 def test_bomb_and_size(self):
  self.scanner.record('x','bomb.zip',zipped([('large.txt',b'a'*2000000)]))
  self.assertIn('COMPRESSION_RATIO_LIMIT',[r.get('rejection') for r in self.rows()])
 def test_depth(self):
  data=b'hello'
  for i in range(6):data=zipped([('nested.zip',data)])
  self.scanner.record('x','a.zip',data);self.assertIn('DEPTH_LIMIT',[r.get('rejection') for r in self.rows()]);self.assertLessEqual(max(r.get('depth',0) for r in self.rows()),5)
 def test_duplicate_ordinals_hash_noexec(self):
  payload=b'raise RuntimeError("MUST_NOT_RUN")\n'
  self.scanner.record('x','a.zip',zipped([('same.py',payload),('same.py',payload)]))
  rows=[r for r in self.rows() if r.get('path')=='same.py'];self.assertEqual([r['member_ordinal'] for r in rows],[0,1]);self.assertEqual(rows[0]['sha256'],rows[1]['sha256']);self.assertEqual(rows[1]['duplicate_of'],rows[0]['record_id'])
 def test_limits_and_codec(self):
  saved=ns.MAX_MEMBERS;ns.MAX_MEMBERS=1
  try:self.scanner.record('x','a.zip',zipped([('a.txt',b'\xff'),('b.txt',b'b')]))
  finally:ns.MAX_MEMBERS=saved
  self.assertIn('PARTIAL_CODEC_ERROR',[r.get('static_status') for r in self.rows()]);self.assertIn('MEMBER_LIMIT',[r.get('rejection') for r in self.rows()])
 def test_resume_and_pending(self):
  originals=self.root/'originals';originals.mkdir();(originals/'a.py').write_text('raise Exception("noexec")')
  inv=[{'id':'a','name':'a.py'},{'id':'b','name':'missing.txt'}]
  self.scanner.scan(inv,originals);n=len(self.rows());ns.Scanner(self.root/'out').scan(inv,originals)
  self.assertEqual(len(self.rows()),n+1);self.assertEqual(self.rows()[-1]['byte_status'],'PENDING_ORIGINAL')
 def test_size_and_total_limits(self):
  old_member,old_total=ns.MAX_MEMBER,ns.MAX_TOTAL
  ns.MAX_MEMBER=10;ns.MAX_TOTAL=5
  try:self.scanner.record('x','a.zip',zipped([('large',b'a'*11),('first',b'abc'),('second',b'def')]))
  finally:ns.MAX_MEMBER,ns.MAX_TOTAL=old_member,old_total
  reasons=[r.get('rejection') for r in self.rows()]
  self.assertIn('MEMBER_SIZE_LIMIT',reasons);self.assertIn('TOTAL_EXPANSION_LIMIT',reasons)
 def test_bulk_manifest_noexpansion(self):
  originals=self.root/'originals';originals.mkdir();(originals/'ChatGPT_Library_Part1.zip').write_bytes(zipped([('never.py',b'raise Exception()')]))
  self.scanner.scan([{'id':'bulk','name':'ChatGPT_Library_Part1.zip'}],originals)
  member=[r for r in self.rows() if r.get('member_ordinal')==0][0]
  self.assertEqual(member['byte_status'],'NOT_HASHED');self.assertEqual(member['static_status'],'MANIFEST_ONLY')
 @unittest.skipUnless(shutil.which('ffprobe'),'ffprobe unavailable')
 def test_actual_media_duration(self):
  originals=self.root/'originals';originals.mkdir();p=originals/'one.wav'
  with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
  self.scanner.scan([{'id':'audio','name':'one.wav'}],originals)
  r=self.rows()[0];self.assertEqual(r['static_status'],'METADATA_ONLY')
  self.assertAlmostEqual(float(r['media_metadata']['format']['duration']),1.0,places=2)
  self.assertEqual(r['semantic_review'],'NOT_PERFORMED')
 def test_canonical_occurrences_dedupe_retries(self):
  originals=self.root/'originals';originals.mkdir()
  data=zipped([('same.txt',b'hello'),('same.txt',b'hello')]);(originals/'a.zip').write_bytes(data)
  inventory=[{'id':'x','name':'a.zip'}]
  self.scanner.record('x','a.zip',data);self.scanner.record('x','a.zip',data)
  first=finalize(self.root/'out',originals,inventory)
  rows=[json.loads(x) for x in (self.root/'out/index.jsonl').read_text().splitlines()]
  self.assertEqual(first['root_record_count'],1);self.assertEqual(len(rows),3)
  self.assertEqual(len({r['occurrence_id'] for r in rows}),3)
  self.assertTrue(all(r['analysis_status']=='COMPLETED' for r in rows))
  self.assertTrue(all(r['semantic_review']=='NOT_PERFORMED' for r in rows))
  second=finalize(self.root/'out',originals,inventory)
  self.assertEqual(second['unique_record_count'],first['unique_record_count'])

if __name__=='__main__':unittest.main()
