from pyrogram import filters

from SONALI_MUSIC import app
from SONALI_MUSIC.misc import SUDOERS
from SONALI_MUSIC.utils.database import add_off, add_on
from SONALI_MUSIC.utils.decorators.language import language
from SONALI_MUSIC.utils.youtube_utils import get_health_status, get_cookiecheck_status


@app.on_message(filters.command(["logger"]) & SUDOERS)
@language
async def logger(client, message, _):
    usage = _["log_1"]
    if len(message.command) != 2:
        return await message.reply_text(usage)
    state = message.text.split(None, 1)[1].strip().lower()
    if state == "enable":
        await add_on(2)
        await message.reply_text(_["log_2"])
    elif state == "disable":
        await add_off(2)
        await message.reply_text(_["log_3"])
    else:
        await message.reply_text(usage)


@app.on_message(filters.command(["cookies"]) & SUDOERS)
@language
async def logger_cookies(client, message, _):
    try:
        await message.reply_document("cookies/logs.csv")
    except Exception:
        pass
    status_text = get_cookiecheck_status()
    await message.reply_text(status_text)


@app.on_message(filters.command(["ythealth", "health"]) & SUDOERS)
async def ythealth_cmd(client, message):
    health_text = get_health_status()
    await message.reply_text(health_text)


@app.on_message(filters.command(["cookiecheck"]) & SUDOERS)
async def cookiecheck_cmd(client, message):
    cookie_text = get_cookiecheck_status()
    await message.reply_text(cookie_text)
