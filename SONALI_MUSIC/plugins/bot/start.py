import time
import random
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
import config
from SONALI_MUSIC import app, YouTube
from SONALI_MUSIC.misc import _boot_
from SONALI_MUSIC.plugins.sudo.sudoers import sudoers_list
from SONALI_MUSIC.utils.database import get_served_chats, get_served_users, get_sudoers
from SONALI_MUSIC.utils import bot_sys_stats
from SONALI_MUSIC.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from SONALI_MUSIC.utils.decorators.language import LanguageStart
from SONALI_MUSIC.utils.formatters import get_readable_time
from SONALI_MUSIC.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS
from strings import get_string
 
NEXIO = [
          "https://litter.catbox.moe/vtsad2y91ytmincf.jpg",
          "https://litter.catbox.moe/4w9ecqcg6gzijzwt.jpg",
          "https://litter.catbox.moe/ql33xyx1bawu1c2v.jpg",
          "https://litter.catbox.moe/wvszrn7kqj0lrme6.jpg",
          "https://litter.catbox.moe/oc71pbepf8cxkk4r.jpg",
          "https://litter.catbox.moe/00ty0hx8cbrs2299.jpg",
          "https://litter.catbox.moe/pdn1i4ze2hl1u6gf.jpg",
          "https://litter.catbox.moe/qcgtbz6keobcc8iz.jpg",
]
 
@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    await add_served_user(message.from_user.id)
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[0:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_photo(
                random.choice(NEXIO),
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
                has_spoiler=True
            )
        if name[0:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
                )
            return
        if name[0:3] == "inf":
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            yt_link = f"https://www.youtube.com/watch?v={query}"
            try:
                track_details, vidid = await YouTube.track(query)
                title = track_details.get("title", "Unknown")
                duration = track_details.get("duration_min", "0:00")
                thumbnail = track_details.get("thumb", "")
                link = track_details.get("link", yt_link)

                searched_text = _["start_6"].format(
                    title, duration, "N/A", "N/A", link, "YouTube", app.mention
                )
                key = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(text=_["S_B_8"], url=link),
                            InlineKeyboardButton(text=_["S_B_9"], url=config.SUPPORT_CHAT),
                        ],
                    ]
                )
                await m.delete()
                if thumbnail:
                    await app.send_photo(
                        chat_id=message.chat.id,
                        photo=thumbnail,
                        caption=searched_text,
                        reply_markup=key,
                        has_spoiler=True,
                    )
                else:
                    await app.send_message(
                        chat_id=message.chat.id,
                        text=searched_text,
                        reply_markup=key,
                        disable_web_page_preview=True,
                    )
            except Exception as e:
                await m.edit_text(f"Failed to fetch track info: {e}")
                return

            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
                )
    else:
        out = private_panel(_)
        baby = await message.reply_text(f"**__ᴅɪηɢ ᴅᴏηɢ.🥀__**")
        await baby.edit_text(f"**__ᴅɪηɢ ᴅᴏηɢ..🥀__**")
        await baby.edit_text(f"**__ᴅɪηɢ ᴅᴏηɢ...🥀__**")
        await baby.edit_text(f"**__ᴅɪηɢ ᴅᴏηɢ....🥀__**")
        await baby.edit_text(f"**__ᴅɪηɢ ᴅᴏηɢ.....🥀__**")
        await baby.edit_text(f"**__sᴛᴧʀᴛɪηɢ.❤️‍🔥__**")
        await baby.edit_text(f"**__sᴛᴧʀᴛɪηɢ..❤️‍🔥__**")
        await baby.edit_text(f"**__sᴛᴧʀᴛɪηɢ...❤️‍🔥__**")
        await baby.edit_text(f"**__sᴛᴧʀᴛɪηɢ....❤️‍🔥__**")
        await baby.edit_text(f"**__sᴛᴧʀᴛɪηɢ.....❤️‍🔥__**")
        await baby.edit_text(f"**__ʙσᴛ sᴛᴧʀᴛєᴅ.💤__**")
        await baby.edit_text(f"**__ʙσᴛ sᴛᴧʀᴛєᴅ..💤__**")
        await baby.edit_text(f"**__ʙσᴛ sᴛᴧʀᴛєᴅ...💤__**")
        await baby.edit_text(f"**__ʙσᴛ sᴛᴧʀᴛєᴅ....💤__**")
        await baby.edit_text(f"**__ʙσᴛ sᴛᴧʀᴛєᴅ.....💤__**")
        await baby.delete()
        
        await message.reply_photo(
            random.choice(NEXIO),
            caption=_["start_2"].format(message.from_user.mention, app.mention),
            reply_markup=InlineKeyboardMarkup(out),
            has_spoiler=True,
        )
        if await is_on_off(2):
            return await app.send_message(
                chat_id=config.LOGGER_ID,
                text=f"{message.from_user.mention} 🚀 Just Started the Bot!.\n\n<b>🆔 Telegram ID :</b> <code>{message.from_user.id}</code>\n<b>🔗 Username:  :</b> @{message.from_user.username}",
            )
 
@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    out = start_panel(_)
    uptime = int(time.time() - _boot_)
    await message.reply_photo(
        random.choice(NEXIO),
        caption=_["start_1"].format(app.mention, get_readable_time(uptime)),
        reply_markup=InlineKeyboardMarkup(out),
        has_spoiler=True,
    )
    return await add_served_chat(message.chat.id)
 
@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except:
                    pass
            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)
                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)
 
                out = start_panel(_)
                await message.reply_photo(
                    random.choice(NEXIO),
                    caption=_["start_3"].format(
                        message.from_user.mention,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                    has_spoiler=True,
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()
        except Exception as ex:
            print(ex)
