"""
Example Pyrogram /play command handler utilizing play_system.py
"""

from pyrogram import Client, filters
from pyrogram.types import Message
from play_system import play_audio_stream


@Client.on_message(filters.command(["play", "vplay"]) & filters.group)
async def play_command_handler(client: Client, message: Message):
    chat_id = message.chat.id

    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> /play [song title or YouTube link]")

    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔎 <i>Searching and preparing audio stream...</i>")

    # Access PyTgCalls client instance (e.g. client.pytgcalls or Sona.one assistant client)
    pytgcalls_client = getattr(client, "pytgcalls", None)

    if not pytgcalls_client:
        return await status_msg.edit_text("❌ PyTgCalls client is not initialized.")

    # Execute play_audio_stream from play_system
    success, title, duration, msg = await play_audio_stream(
        chat_id=chat_id,
        query=query,
        pytgcalls_client=pytgcalls_client,
    )

    if success:
        await status_msg.edit_text(
            f"🎶 <b>Now Playing:</b> {title}\n"
            f"⏱ <b>Duration:</b> {duration}\n\n"
            f"✅ {msg}"
        )
    else:
        await status_msg.edit_text(f"❌ <b>Error:</b> {msg}")
