import asyncio, sys
sys.path.insert(0, '.')
from services.rosreestr import RosreestrClient

async def test():
    c = RosreestrClient()
    r = await c.get_cadastral_info('29:01:140602:391')
    print(r)
    await c.close()

asyncio.run(test())
