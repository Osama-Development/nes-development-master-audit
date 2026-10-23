"""Finalize append-only scan records, filling actual file-backed media metadata."""
import argparse,json,subprocess,hashlib
from collections import Counter
from pathlib import Path
from new_scan import Scanner,MEDIA_EXT

def finalize(output,originals,inventory):
 output=Path(output); originals=Path(originals);scanner=Scanner(output)
 latest={};raw_count=0
 with scanner.records.open() as f:
  for line in f:
   try:
    raw_count+=1
    r=json.loads(line)
    if not r.get('parent_record_id'):
     r['record_id']=r['source_id']+':root:original'
    elif r['parent_record_id']==r['source_id']+':original':r['parent_record_id']=r['source_id']+':root:original'
    latest[r['record_id']]=r
   except (ValueError,KeyError):pass
 mapping={str(x.get('library_file_id') or x.get('file_id') or x.get('id') or x['name']):x.get('path',x['name']).lstrip('/') for x in inventory}
 repairs=0
 for r in list(latest.values()):
  if r.get('type')!='media':continue
  if not r.get('parent_record_id'):
   path=originals/mapping.get(r['source_id'],r['path'])
   try:
    probe=subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-show_entries','format=duration:stream=codec_name,codec_type,width,height,duration','-of','json',str(path.resolve())],capture_output=True,timeout=30,check=True)
    r['media_metadata']=json.loads(probe.stdout);r['media_probe']='ffprobe_original_file'
    r['static_status']='METADATA_ONLY'
   except Exception as e:r['static_status']='PARTIAL';r['error_type']=type(e).__name__
  meta=r.get('media_metadata',{})
  if r.get('static_status')=='METADATA_ONLY' and not ('duration' in meta.get('format',{}) or any('duration'in x for x in meta.get('streams',[]))):r['static_status']='PARTIAL_DURATION_UNAVAILABLE'
  scanner.emit(r);latest[r['record_id']]=r;repairs+=1
 # Stable occurrence identity uses source, archive ancestry and member ordinal.
 memo={}
 def occurrence(r):
  rid=r['record_id']
  if rid in memo:return memo[rid]
  parent=r.get('parent_record_id')
  if not parent:key=[r['source_id'],'original']
  elif r.get('member_ordinal') is not None:key=[r['source_id'],occurrence(latest[parent]) if parent in latest else parent,r['member_ordinal']]
  else:key=[r['source_id'],parent,rid.rsplit(':',1)[-1]]
  memo[rid]='occ-'+hashlib.sha256(json.dumps(key,separators=(',',':')).encode()).hexdigest()
  return memo[rid]
 canonical={}
 for r in latest.values():
  r['occurrence_id']=occurrence(r)
  if r.get('parent_record_id') in latest:r['parent_occurrence_id']=occurrence(latest[r['parent_record_id']])
  if r.get('duplicate_of') in latest:r['duplicate_occurrence_id']=occurrence(latest[r['duplicate_of']])
  status=r.get('static_status','NOT_SUPPORTED')
  r['analysis_scope']='STATIC_ONLY'
  r['analysis_status']=('COMPLETED' if status in {'INDEXED','DIRECTORY'} else 'UNSUPPORTED' if status in {'NOT_SUPPORTED','UNSUPPORTED_SITE'} else 'PENDING' if status=='PENDING' else 'FAILED' if status=='FAILED' else 'PARTIAL')
  if not r.get('parent_record_id'):r['source_relative_path']=mapping.get(r['source_id'],r['path'])
  canonical[r['occurrence_id']]=r
 latest=canonical
 incomplete_sources={r['source_id'] for r in latest.values() if r.get('parent_record_id') and r['analysis_status']!='COMPLETED'}
 for r in latest.values():
  if not r.get('parent_record_id') and r['source_id'] in incomplete_sources and r['analysis_status']=='COMPLETED':r['analysis_status']='PARTIAL';r['descendant_static_analysis_incomplete']=True
 with (output/'index.jsonl').open('w') as f:
  for r in latest.values():f.write(json.dumps(r,ensure_ascii=False)+'\n')
 roots=[r for r in latest.values() if not r.get('parent_record_id')]
 with (output/'root_index.jsonl').open('w') as f:
  for r in roots:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 summary={'semantic_review':'NOT_PERFORMED','historical_raw_record_count':raw_count+repairs,'historical_or_retry_records_beyond_current_unique':raw_count+repairs-len(latest),'historical_raw_record_count_before_final_media_append':raw_count,'final_media_append_count':repairs,'unique_record_count':len(latest),'root_analysis_status_counts':dict(Counter(r['analysis_status'] for r in roots)),'all_analysis_status_counts':dict(Counter(r['analysis_status'] for r in latest.values())),'root_record_count':len(roots),'root_static_status_counts':dict(Counter(r.get('static_status') for r in roots)),'root_byte_status_counts':dict(Counter(r.get('byte_status') for r in roots)),'all_static_status_counts':dict(Counter(r.get('static_status') for r in latest.values())),'rejection_counts':dict(Counter(r.get('rejection') for r in latest.values() if r.get('rejection'))),'duplicate_record_count':sum('duplicate_of'in r for r in latest.values()),'media_metadata_records_finalized':repairs,'scope':'Static bytes, archive inventory and typed metadata only. No source execution. Bulk backup payloads not expanded. Images not visually reviewed; audio/video content not semantically reviewed. Rejected/unsupported/partial records remain incomplete.'}
 (output/'final_summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--originals',required=True);p.add_argument('--inventory',required=True);a=p.parse_args()
 print(json.dumps(finalize(a.output,a.originals,json.loads(Path(a.inventory).read_text()))))
