from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from SONALI_MUSIC import app
from config import BOT_USERNAME
from SONALI_MUSIC.utils.errors import capture_err
import httpx 
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

start_txt = """**
<u>❃ ᴡєʟᴄσϻє ᴛᴏ sᴘɪᴄʏ ɴєᴛᴡσʀᴋ ʀєᴘσs ❃</u>
 
✼ ʀєᴘᴏ ɪs ηᴏᴡ ᴘʀɪᴠᴧᴛє ᴅᴜᴅє 😌
 
❉  ʏᴏᴜ ᴄᴧη мʏ ᴜsє ᴘᴜʙʟɪᴄ ʀєᴘσs !!  

✼ || [˹  ɴᴇᴛᴡᴏʀᴋ˼ 💞](https://t.me/II_MUSIC_BOT_UPDATE_II) ||
 
❊ ʀᴜη 24x7 ʟᴧɢ ϝʀєє ᴡɪᴛʜσᴜᴛ sᴛσᴘ**
"""




@app.on_message(filters.command("repo"))
async def start(_, msg):
    buttons = [
        [ 
          InlineKeyboardButton("✙ ᴧᴅᴅ ϻє вᴧʙʏ ✙", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")
        ],
        [
          InlineKeyboardButton("• ɴєᴛᴡᴏʀᴋ •", url="https://t.me/II_MUSIC_BOT_UPDATE_II"),
          InlineKeyboardButton("• 𝛅ᴜᴘᴘσʀᴛ •", url="https://t.me/II_ALONE_BOY_Il"),
          ],
[
InlineKeyboardButton("• ᴧʟʟ ʙσᴛѕ •", url=f"https://t.me/II_MUSIC_BOT_UPDATE_II"),

        ]]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await msg.reply_photo(
        photo="https://litter.catbox.moe/xr9jf82b2umeke7j.jpg",
        caption=start_txt,
        reply_markup=reply_markup
    )
