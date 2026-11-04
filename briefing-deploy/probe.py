import asyncio,json,time,os
from datetime import datetime,UTC
from zoneinfo import ZoneInfo
os.environ['CHARTAGENT_BRIEFING_DB']='/tmp/briefing-probe.sqlite3'
from app import briefings as b
async def main():
    market=b.InsightSentryClient(b.get_settings())
    for sid in ['BTCUSD','AAPL','XAUUSD']:
        terms=b.keywords(b.INSTRUMENTS[sid])
        raw=await market._get('/v3/newsfeed',params={'keywords':','.join(terms),'limit':'40','page':'1','from':datetime.fromtimestamp(time.time()-86400,UTC).strftime('%Y-%m-%d')})
        sources=await b.collect_sources(sid)
        print('SOURCES',json.dumps({'symbol':sid,'keywords':terms,'raw_count':len(raw.get('data',[])),'meta':{k:v for k,v in raw.items() if k!='data'},'accepted':len(sources),'oldest_hours':round((time.time()-min(s['published_at'] for s in sources))/3600,2) if sources else None,'titles':[s['title'] for s in sources[:4]]}),flush=True)
        assert sources, sid
    repo=b.repository()
    repo.select('probe',b.Preferences(instruments=['BTCUSD'],language='ko'))
    job=repo.claim()
    story=await b.generate(job)
    repo.finish(job,story)
    translated=await b.translate({'base_id':story['id'],'language':'en-US'})
    assert translated['sources']==story['sources'] and translated['canonical_id']==story['id']
    reset=b.next_briefing_reset(story['source_window_end'])
    print('BRIEFING',json.dumps({'coverage':story['coverage'],'title_ko':story['title'],'title_en':translated['title'],'next_reset_ny':datetime.fromtimestamp(reset,ZoneInfo('America/New_York')).isoformat(),'translation_reuses_sources':True,'push_configured':b.push_configured()},ensure_ascii=False),flush=True)
asyncio.run(main())
