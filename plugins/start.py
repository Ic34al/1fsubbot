@Bot.on_message(filters.command("start") & filters.private)
async def not_joined(client: Client, message: Message):

    buttons = []

    if FORCE_SUB_CHANNEL:
        buttons.append([
            InlineKeyboardButton(
                text="ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 1",
                url=client.invitelink
            )
        ])

    if FORCE_SUB_CHANNEL2:
        buttons.append([
            InlineKeyboardButton(
                text="ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 2",
                url=client.invitelink2
            )
        ])

    # Optional extra channel button
    buttons.append([
        InlineKeyboardButton(
            text="📢 Updates",
            url="https://t.me/+0VmAgFtSHGIxNjg1"
        )
    ])

    if len(message.command) > 1:
        buttons.append([
            InlineKeyboardButton(
                text="🔄 Reload",
                url=(
                    f"https://t.me/{client.username}"
                    f"?start={message.command[1]}"
                )
            )
        ])

    await message.reply_photo(
        photo=FORCE_PIC,
        caption=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=(
                None
                if not message.from_user.username
                else "@" + message.from_user.username
            ),
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=InlineKeyboardMarkup(buttons)
    )
