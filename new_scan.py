"""Bounded static inventory. Never imports, evaluates or launches scanned source.
Run with --inventory --originals --output; JSONL is flushed per source for resume.
"""
import argparse, hashlib, io, json, os, re, stat, subprocess, tarfile, zipfile
from pathlib import Path, PurePosixPath

MAX_DEPTH=4
MAX_MEMBERS=100000
MAX_TOTAL=2*1024**3
MAX_MEMBER=32*1024**2
MAX_RATIO=1000
TEXT_EXT={'.txt','.md','.markdown','.html','.css','.js','.ts','.tsx','.jsx','.py','.sql','.json','.yaml','.yml','.xml','.csv','.sh','.toml','.ini','.svg','.c','.cpp','.java','.rs','.go'}
IMAGE_EXT={'.png','.jpg','.jpeg','.gif','.webp','.bmp','.tiff','.ico'}
MEDIA_EXT={'.mp4','.mov','.webm','.mkv','.mp3','.wav','.ogg','.m4a','.flac','.avi'}

def digest_file(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
 return h.hexdigest()

def unsafe_name(name):
 p=PurePosixPath(name.replace('\\','/'))
 return p.is_absolute() or '..' in p.parts or bool(re.match(r'^[A-Za-z]:',name)) or '\x00' in name

class Scanner:
 def __init__(self, output):
  self.output=Path(output); self.output.mkdir(parents=True,exist_ok=True)
  self.records=self.output/'records.jsonl'; self.done=self.output/'completed.jsonl'
  self.seen={}; self.count=0; self.total=0
  if self.records.exists():
   for line in self.records.read_text().splitlines():
    try:
     r=json.loads(line)
     if r.get('sha256'): self.seen.setdefault(r['sha256'],r['record_id'])
     if r.get('member_ordinal') is not None:
      self.count+=1
      if r.get('byte_status')=='HASHED':self.total+=r.get('byte_size',0)
    except ValueError: pass
 def emit(self,r):
  r.setdefault('semantic_review','NOT_PERFORMED')
  status=r.get('static_status','NOT_SUPPORTED')
  r['analysis_scope']='STATIC_ONLY'
  r['analysis_status']=('COMPLETED' if status in {'INDEXED','DIRECTORY'} else 'UNSUPPORTED' if status in {'NOT_SUPPORTED','UNSUPPORTED_SITE'} else 'PENDING' if status=='PENDING' else 'FAILED' if status=='FAILED' else 'PARTIAL')
  if r.get('sha256'):
   prior=self.seen.setdefault(r['sha256'],r['record_id'])
   if prior!=r['record_id']: r['duplicate_of']=prior
  with self.records.open('a') as f: f.write(json.dumps(r,ensure_ascii=False)+'\n'); f.flush()
  if not r.get('parent_record_id'):
   with (self.output/'roots.jsonl').open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 def record(self, source, name, data, parent=None, ordinal=None, depth=0, bulk=False, probe_path=None):
  rid=f'{source}:{parent or "root"}:{ordinal if ordinal is not None else "original"}'
  r={'record_id':rid,'source_id':source,'path':name,'parent_record_id':parent,'member_ordinal':ordinal,'depth':depth,'sha256':hashlib.sha256(data).hexdigest(),'byte_size':len(data),'byte_status':'HASHED','static_status':'NOT_SUPPORTED','semantic_review':'NOT_PERFORMED'}
  ext=Path(name).suffix.lower()
  try:
   iszip=zipfile.is_zipfile(io.BytesIO(data))
   istar=False
   if not iszip:
    try:
     with tarfile.open(fileobj=io.BytesIO(data),mode='r:*'): istar=True
    except tarfile.TarError: pass
   if iszip or istar:
    r['type']='archive'; r['static_status']='MANIFEST_ONLY' if bulk else 'INDEXED'; self.emit(r)
    self.archive(source,data,rid,depth,bulk,iszip); return r
   if ext in TEXT_EXT:
    r['type']='text'
    try: text=data.decode('utf-8-sig'); r['encoding']='utf-8'
    except UnicodeError:
     r['static_status']='PARTIAL_CODEC_ERROR'; self.emit(r); return r
    r['line_count']=len(text.splitlines()); r['static_status']='INDEXED'
    r['symbols']=sorted(set(re.findall(r'\b(?:async\s+)?(?:function|class|def)\s+([A-Za-z_$][\w$]*)',text)))[:10000]
    r['dependencies']=sorted(set(re.findall(r'''(?:from\s+|import\s*\(?\s*|require\(\s*)["']([\w@./-]+)["']''',text)))[:10000]
    r['sql_tables']=sorted(set(re.findall(r'\b(?:CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|INSERT\s+INTO|UPDATE|FROM|JOIN)\s+[`"\[]?([\w.]+)',text,re.I)))[:10000]
   elif ext in IMAGE_EXT:
    r['type']='image'
    try:
     from PIL import Image
     with Image.open(io.BytesIO(data)) as image: r['dimensions']=list(image.size); r['format']=image.format
     r['static_status']='METADATA_ONLY'
    except Exception as e: r['static_status']='PARTIAL';r['error_type']=type(e).__name__
   elif ext in MEDIA_EXT:
    r['type']='media'
    try:
     probe=subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe' if probe_path else 'pipe','-show_entries','format=duration:stream=codec_name,codec_type,width,height,duration','-of','json',str(probe_path.resolve()) if probe_path else 'pipe:0'],input=None if probe_path else data,capture_output=True,timeout=30,check=True)
     r['media_metadata']=json.loads(probe.stdout);r['static_status']='METADATA_ONLY' if ('duration' in r['media_metadata'].get('format',{}) or any('duration' in stream for stream in r['media_metadata'].get('streams',[]))) else 'PARTIAL_DURATION_UNAVAILABLE'
    except Exception as e:r['static_status']='PARTIAL';r['error_type']=type(e).__name__
   else: r['type']='binary'
  except Exception as e: r['static_status']='PARTIAL';r['error_type']=type(e).__name__
  self.emit(r);return r
 def archive(self,source,data,parent,depth,bulk,iszip):
  try:
   obj=zipfile.ZipFile(data if isinstance(data,Path) else io.BytesIO(data)) if iszip else (tarfile.open(data,mode='r:*') if isinstance(data,Path) else tarfile.open(fileobj=io.BytesIO(data),mode='r:*'))
   with obj:
    members=obj.infolist() if iszip else obj
    for ordinal,m in enumerate(members):
     name=m.filename if iszip else m.name; size=m.file_size if iszip else m.size
     rid=f'{source}:{parent}:{ordinal}'
     row={'record_id':rid,'source_id':source,'path':name,'parent_record_id':parent,'member_ordinal':ordinal,'depth':depth+1,'byte_size':size,'byte_status':'NOT_HASHED','static_status':'MANIFEST_ONLY' if bulk else 'REJECTED'}
     self.count+=1
     reason=None
     mode=(m.external_attr>>16) if iszip else 0
     if unsafe_name(name): reason='UNSAFE_PATH'
     elif (stat.S_ISLNK(mode) if iszip else (m.issym() or m.islnk())): reason='LINK'
     elif (m.is_dir() if iszip else m.isdir()): row['static_status']='DIRECTORY';self.emit(row);continue
     elif not iszip and not m.isfile():reason='SPECIAL_MEMBER'
     elif self.count>MAX_MEMBERS:reason='MEMBER_LIMIT'
     elif size>MAX_MEMBER:reason='MEMBER_SIZE_LIMIT'
     elif self.total+size>MAX_TOTAL:reason='TOTAL_EXPANSION_LIMIT'
     elif iszip and size/max(1,m.compress_size)>MAX_RATIO:reason='COMPRESSION_RATIO_LIMIT'
     elif depth>=MAX_DEPTH:reason='DEPTH_LIMIT'
     if reason:
      row['rejection']=reason;row['static_status']='REJECTED';self.emit(row)
      if not iszip and reason in {'MEMBER_SIZE_LIMIT','TOTAL_EXPANSION_LIMIT','MEMBER_LIMIT','DEPTH_LIMIT'}:
       self.emit({'record_id':parent+':tar_manifest_incomplete','source_id':source,'parent_record_id':parent,'static_status':'PARTIAL_LIMIT_STOPPED','reason':'Remaining TAR headers cannot safely be enumerated across oversized skipped payloads'})
       return
      continue
     if bulk:self.emit(row);continue
     self.total+=size
     try:
      f=obj.open(m) if iszip else obj.extractfile(m)
      with f: content=f.read(MAX_MEMBER+1)
      if len(content)!=size:row['rejection']='SIZE_MISMATCH';self.emit(row);continue
      self.record(source,name,content,parent,ordinal,depth+1)
     except Exception as e:row['static_status']='PARTIAL';row['error_type']=type(e).__name__;self.emit(row)
  except Exception as e:self.emit({'record_id':parent+':archive_error','source_id':source,'parent_record_id':parent,'static_status':'PARTIAL','error_type':type(e).__name__})
 def scan(self, inventory, originals, batch_limit=0):
  done=set()
  if self.done.exists():
   for line in self.done.read_text().splitlines():
    try:done.add(json.loads(line)['resume_key'])
    except ValueError:pass
  processed=0
  for item in inventory:
   source=item.get('library_file_id') or item.get('file_id') or item.get('id') or item['name']
   name=item.get('name',''); relative=item.get('path',name).lstrip('/'); path=Path(originals)/relative
   key=source+':'+str(item.get('modified_at'))+':'+relative
   if key in done:continue
   if batch_limit and processed>=batch_limit:break
   if item.get('kind')=='site' or item.get('library_artifact_type')=='site':
    self.emit({'record_id':source+':original','source_id':source,'path':name,'byte_status':'NOT_AVAILABLE','static_status':'UNSUPPORTED_SITE'});continue
   if unsafe_name(relative) or not path.is_file() or path.is_symlink():
    self.emit({'record_id':source+':original','source_id':source,'path':name,'byte_status':'PENDING_ORIGINAL','static_status':'PENDING'});continue
   processed+=1
   if path.stat().st_size>MAX_MEMBER:
    sha=digest_file(path)
    # Archives may be large on disk. Stream hash every byte but do not materialize oversized non-backup input.
    if not name.startswith('ChatGPT_Library_Part') and (zipfile.is_zipfile(path) or tarfile.is_tarfile(path)):
     r={'record_id':source+':root:original','source_id':source,'path':name,'sha256':sha,'byte_size':path.stat().st_size,'byte_status':'HASHED','static_status':'INDEXED','type':'archive'};self.emit(r)
     self.archive(source,path,r['record_id'],0,False,zipfile.is_zipfile(path))
     with self.done.open('a') as f:f.write(json.dumps({'resume_key':key,'source_id':source})+'\n')
     continue
    if Path(name).suffix.lower() in MEDIA_EXT:
     r={'record_id':source+':root:original','source_id':source,'path':name,'sha256':sha,'byte_size':path.stat().st_size,'byte_status':'HASHED','static_status':'PARTIAL','type':'media'}
     try:
      probe=subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_entries','format=duration:stream=codec_name,codec_type,width,height,duration','-of','json',str(path.resolve())],capture_output=True,timeout=30,check=True)
      r['media_metadata']=json.loads(probe.stdout);r['static_status']='METADATA_ONLY' if ('duration' in r['media_metadata'].get('format',{}) or any('duration' in stream for stream in r['media_metadata'].get('streams',[]))) else 'PARTIAL_DURATION_UNAVAILABLE'
     except Exception as e:r['error_type']=type(e).__name__
     self.emit(r)
     with self.done.open('a') as f:f.write(json.dumps({'resume_key':key,'source_id':source})+'\n')
     continue
    if not name.startswith('ChatGPT_Library_Part'):
     self.emit({'record_id':source+':original','source_id':source,'path':name,'sha256':sha,'byte_size':path.stat().st_size,'byte_status':'HASHED','static_status':'PARTIAL_ORIGINAL_SIZE_LIMIT'});continue
   bulk=name.startswith('ChatGPT_Library_Part')
   if bulk:
    r={'record_id':source+':original','source_id':source,'path':name,'sha256':digest_file(path),'byte_size':path.stat().st_size,'byte_status':'HASHED','static_status':'MANIFEST_ONLY','type':'archive'};self.emit(r)
    # Enumerate member headers only; never expand bulk backup payloads.
    self.archive(source,path,r['record_id'],0,True,zipfile.is_zipfile(path))
   else:
    r=self.record(source,name,path.read_bytes(),probe_path=path)

   with self.done.open('a') as f:f.write(json.dumps({'resume_key':key,'source_id':source})+'\n');f.flush()
  counts={}
  with self.records.open() as f:
   for line in f:
    try:
     r=json.loads(line);status=r.get('static_status','UNKNOWN');counts[status]=counts.get(status,0)+1
    except ValueError:counts['MALFORMED_JSONL_LINE']=counts.get('MALFORMED_JSONL_LINE',0)+1
  summary={'record_status_counts':counts,'semantic_review':'NOT_PERFORMED','processed_this_run':processed,'archive_members_considered_total':self.count,'expanded_bytes_total':self.total,'limits':{'depth':MAX_DEPTH,'members':MAX_MEMBERS,'expanded_bytes':MAX_TOTAL,'member_bytes':MAX_MEMBER,'ratio':MAX_RATIO}}
  (self.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
  return summary

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--originals',required=True);p.add_argument('--output',required=True);p.add_argument('--batch-limit',type=int,default=0);a=p.parse_args()
 print(json.dumps(Scanner(a.output).scan(json.loads(Path(a.inventory).read_text()),a.originals,a.batch_limit)))
