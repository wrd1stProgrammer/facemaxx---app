from pathlib import Path
p=Path('/app/app/main.py')
s=p.read_text()
assert 'briefings_router' not in s
anchor='from __future__ import annotations\n'
assert anchor in s
s=s.replace(anchor,anchor+'import asyncio\nfrom contextlib import suppress\nfrom app.briefings import router as briefings_router, worker as briefing_worker\n',1)
old='    yield\n    await analytics.close()'
assert old in s
s=s.replace(old,'''    task = asyncio.create_task(briefing_worker())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await analytics.close()''',1)
s=s.replace('app.include_router(news_workspace_router)','app.include_router(news_workspace_router)\napp.include_router(briefings_router)',1)
p.write_text(s)
