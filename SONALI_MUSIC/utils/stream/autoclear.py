import os

from config import autoclean


async def auto_clean(popped):
    try:
        rem = popped["file"]
        autoclean.remove(rem)
        count = autoclean.count(rem)
        if count == 0:
            if not any(prefix in rem for prefix in ("vid_", "live_", "index_")):
                if os.path.exists(rem):
                    try:
                        os.remove(rem)
                    except Exception:
                        pass
    except:
        pass
