from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from SONALI_MUSIC import app
import config
from config import BOT_USERNAME
from SONALI_MUSIC.utils.errors import capture_err
import httpx 

start_txt = f"""**
<u>❃ ᴡєʟᴄσϻє ᴛᴏ sᴘɪᴄʏ ɴєᴛᴡσʀᴋ ʀєᴘσs ❃</u>
 
✼ ʀєᴘᴏ ɪs ηᴏᴡ ᴘʀɪᴠᴧᴛє ᴅᴜᴅє 😌
 
❉  ʏᴏᴜ ᴄᴧη мʏ ᴜsє ᴘᴜʙʟɪᴄ ʀєᴘσs !!  

✼ || [˹  ɴᴇᴛᴡᴏʀᴋ˼ 💞]({config.SUPPORT_CHANNEL}) ||
 
❊ ʀᴜη 24x7 ʟᴧɢ ϝʀєє ᴡɪᴛʜσᴜᴛ sᴛσᴘ**
"""




@app.on_message(filters.command("repo"))
async def start(_, msg):
    buttons = [
        [ 
          InlineKeyboardButton("✙ ᴧᴅᴅ ϻє вᴧʙʏ ✙", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")
        ],
        [
          InlineKeyboardButton("• ɴєᴛᴡᴏʀᴋ •", url=config.SUPPORT_CHANNEL),
          InlineKeyboardButton("• 𝛅ᴜᴘᴘσʀᴛ •", url=config.SUPPORT_CHAT),
          ],
[
InlineKeyboardButton("• ᴧʟʟ ʙσᴛѕ •", url=config.SUPPORT_CHANNEL),

        ]]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await msg.reply_photo(
        photo=config.START_IMG_URL,
        caption=start_txt,
        reply_markup=reply_markup
    )
