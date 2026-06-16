import logging
import random
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.error import Forbidden
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, ChatMemberHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TOKEN = "8709199396:AAHNOUYFtU8lL9HfTEzCao0nuuS4VcLu91M"
ADMIN_IDS = [8782524249, 5030058973] # Zenith Tay Za Lin Maung's ID
USER_LIST_FILE = "users.txt"
CHAT_LIST_FILE = "chats.txt"
START_IMAGE_FILE = "start_image.txt"
BROADCAST_DELAY_SECONDS = 0.8
GROUP_TYPES = {"group", "supergroup"}

# Game State Storage (Independent per Group)
games = {}

HELP_TEXT = (
    "📜 **Werewolf ဂိမ်းဆော့ကစားနည်း အပြည့်အစုံ**\n\n"
    "ဒီဂိမ်းဟာ Among Us လိုမျိုးပဲ ရွာသားတွေကြားထဲမှာ ပုန်းနေတဲ့ ဝံပုလွေတွေကို ရှာဖွေရတဲ့ ဂိမ်းဖြစ်ပါတယ်။\n\n"
    "🎭 **ဇာတ်ကောင်များ (Roles):**\n"
    "🐺 **ဝံပုလွေ (Werewolf):** ညဘက်မှာ ရွာသားတစ်ယောက်ကို ရွေးချယ်သတ်ဖြတ်ရပါမယ်။ ရွာသားအရေအတွက်နဲ့ ဝံပုလွေအရေအတွက် တူသွားရင် ဝံပုလွေနိုင်ပါတယ်။\n"
    "👨‍🌾 **ရွာသား (Villager):** အထူးစွမ်းအားမရှိပေမယ့် နေ့ဘက်မှာ ဝံပုလွေလို့ သံသယရှိသူကို မဲပေးဖယ်ရှားရပါမယ်။ ဝံပုလွေအားလုံးသေရင် ရွာသားနိုင်ပါတယ်။\n"
    "🔮 **ရှေ့ဖြစ်ဟောဆရာ (Seer):** ညဘက်မှာ လူတစ်ယောက်ကို ရွေးပြီး ဝံပုလွေ ဟုတ်မဟုတ် စစ်ဆေးနိုင်ပါတယ်။\n\n"
    "⏰ **ဂိမ်းအဆင့်ဆင့် (Phases):**\n"
    "၁။ **ညဘက် (၃ မိနစ်):** ဝံပုလွေတွေက ဘော့ဆီမှာ Private Message နဲ့ လူသတ်ရပါမယ်။\n"
    "၂။ **နေ့ဘက်:** ဘော့က အသတ်ခံရသူကို ကြေညာပါမယ်။\n"
    "၃။ **မဲပေးချိန် (၃ မိနစ်):** Group ထဲမှာ လူတိုင်း တိုင်ပင်ပြီး ဝံပုလွေလို့ ထင်ရသူကို မဲပေးရပါမယ်။\n\n"
    "🎮 **Commands:**\n"
    "- `/newgame`: ဂိမ်းအသစ်စတင်ရန် (Group ထဲမှာသုံးပါ)\n"
    "- `/join`: ဂိမ်းထဲဝင်ရန်\n"
    "- `/startgame`: လူစုံရင် ဂိမ်းစတင်ရန်\n"
    "- `/end`: လက်ရှိဂိမ်းကို ရပ်ရန်\n"
    "- `/help`: ဆော့နည်းပြန်ကြည့်ရန်\n\n"
    "💡 **အကြံပြုချက်:** မလုပ်တတ်ပါက @Offcial_Lin_Maung လာပြောပြီးသင်ခိုင်းလို့ရပါသည်"
)

def save_user(user_id):
    if not os.path.exists(USER_LIST_FILE):
        with open(USER_LIST_FILE, "w") as f:
            f.write(str(user_id) + "\n")
        return
    
    with open(USER_LIST_FILE, "r") as f:
        users = f.read().splitlines()
    
    if str(user_id) not in users:
        with open(USER_LIST_FILE, "a") as f:
            f.write(str(user_id) + "\n")

def read_id_file(path):
    if not os.path.exists(path):
        return []

    with open(path, "r") as f:
        ids = []
        for line in f.read().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ids.append(int(line))
            except ValueError:
                logger.warning("Skipping invalid chat id %r in %s", line, path)
        return ids

def save_chat(chat_id):
    chats = read_id_file(CHAT_LIST_FILE)
    if chat_id in chats:
        return

    with open(CHAT_LIST_FILE, "a") as f:
        f.write(str(chat_id) + "\n")

def remove_chat(chat_id):
    for path in (CHAT_LIST_FILE, USER_LIST_FILE):
        chats = [cid for cid in read_id_file(path) if cid != chat_id]
        with open(path, "w") as f:
            for cid in chats:
                f.write(str(cid) + "\n")

def load_start_image():
    if not os.path.exists(START_IMAGE_FILE):
        return None

    with open(START_IMAGE_FILE, "r") as f:
        value = f.read().strip()
    return value or None

def save_start_image(image):
    with open(START_IMAGE_FILE, "w") as f:
        f.write(image.strip())

def describe_game_status(status):
    labels = {
        "joining": "ကစားသမား စုနေဆဲ",
        "starting": "ဂိမ်းစတင်နေဆဲ",
        "night": "ညအချိန်",
        "day": "နေ့အချိန်",
        "voting": "မဲပေးချိန်",
    }
    return labels.get(status, status)

class WerewolfGame:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = {} # user_id: {name, role, alive}
        self.status = "joining" # joining, night, day, voting
        self.night_kills = {} # victim_id: count
        self.day_votes = {} # victim_id: count
        self.voted_users = set()
        self.phase_task = None

    def add_player(self, user_id, name):
        if user_id not in self.players:
            self.players[user_id] = {"name": name, "role": None, "alive": True}
            return True
        return False

    def get_alive_players(self):
        return {uid: p for uid, p in self.players.items() if p['alive']}

    def check_winner(self):
        alive = self.get_alive_players()
        wolves = [p for p in alive.values() if p['role'] == 'werewolf']
        villagers = [p for p in alive.values() if p['role'] != 'werewolf']
        
        if len(wolves) == 0:
            return "villagers"
        if len(wolves) >= len(villagers):
            return "werewolves"
        return None

def schedule_game_phase(chat_id, coro):
    game = games.get(chat_id)
    if not game:
        return

    task = asyncio.create_task(coro)
    game.phase_task = task

    def log_phase_result(done_task):
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.debug("Game phase task cancelled for chat %s", chat_id)
        except Exception:
            logger.exception("Game phase task crashed for chat %s", chat_id)

    task.add_done_callback(log_phase_result)

async def send_private_message(context, user_id, text, **kwargs):
    try:
        await context.bot.send_message(chat_id=user_id, text=text, **kwargs)
        return True
    except Forbidden:
        logger.info("Cannot DM user %s; user has not started the bot or blocked it", user_id)
        return False
    except Exception:
        logger.exception("Could not send private message to user %s", user_id)
        return False

async def is_bot_admin(context, chat_id):
    try:
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=context.bot.id)
    except Exception:
        logger.exception("Could not check bot admin status in chat %s", chat_id)
        return False

    return member.status in ("administrator", "creator")

async def ensure_game_chat(update, context):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        if update.message:
            await update.message.reply_text("❌ ဒီ game command ကို Group ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return False

    if chat.type not in GROUP_TYPES:
        if update.message:
            await update.message.reply_text("❌ ဒီ game command ကို Group/Supergroup ထဲမှာပဲ သုံးလို့ရပါတယ်။")
        return False

    save_chat(chat.id)
    if not await is_bot_admin(context, chat.id):
        if update.message:
            await update.message.reply_text(
                "⚠️ Game command တွေသုံးဖို့ Bot ကို Group Admin ပေးထားဖို့လိုပါတယ်။\n"
                "Bot ကို admin လုပ်ပြီးမှ ပြန်စမ်းပါ။"
            )
        return False

    return True

async def is_game_group_allowed(context, chat_id):
    return await is_bot_admin(context, chat_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    save_chat(chat.id)
    
    # Check if this is a new user/group to notify admin only once
    is_new = False
    if not os.path.exists(USER_LIST_FILE):
        is_new = True
    else:
        with open(USER_LIST_FILE, "r") as f:
            users = f.read().splitlines()
        if str(user.id if chat.type == "private" else chat.id) not in users:
            is_new = True
            
    save_user(user.id if chat.type == "private" else chat.id)
    
    # Admin Notification (Log format - Only for first time)
    if is_new:
        for admin_id in ADMIN_IDS:
            try:
                if chat.type == "private":
                    log_msg = f"New User Log\n\nID: {user.id}\nName: @{user.username if user.username else 'None'} | {user.first_name}"
                else:
                    log_msg = f"New Group Log\n\nID: {chat.id}\nGroup Name: {chat.title}\nAdded by: @{user.username if user.username else 'None'} | {user.first_name}"
                
                await context.bot.send_message(chat_id=admin_id, text=log_msg)
            except Exception:
                logger.exception("Could not notify admin %s about new chat/user", admin_id)

    bot_username = context.bot.username
    welcome_text = (
        "👋 **Werewolf Myanmar Bot မှ ကြိုဆိုပါတယ်!**\n\n"
        "ဒီဘော့ဟာ Among Us လိုမျိုး သူငယ်ချင်းတွေနဲ့အတူ ဝံပုလွေရှာတမ်းကစားရတဲ့ဂိမ်းဖြစ်ပါတယ်။\n\n"
        "အောက်ပါ ခလုတ်များကို အသုံးပြု၍ ကျွန်ုပ်တို့၏ Community တွင် ပါဝင်နိုင်ပါသည်။"
    )
    keyboard = [
        [InlineKeyboardButton("📢 Channel", url="https://t.me/Lin_Maung_Shop"),
         InlineKeyboardButton("👥 Group", url="https://t.me/+hKJK8SBA9QIwNDM1")],
        [InlineKeyboardButton("👨‍💻 Owner", url="https://t.me/Offcial_Lin_Maung")],
        [InlineKeyboardButton("➕ Group ထဲသို့ ထည့်ရန်", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("📖 ဆော့ကစားနည်း ဖတ်ရန်", callback_data="show_help")]
    ]
    start_image = load_start_image()
    if start_image:
        try:
            await update.message.reply_photo(
                photo=start_image,
                caption=welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
            )
            return
        except Exception:
            logger.exception("Could not send configured start image")

    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def start_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ သင်ဟာ Admin မဟုတ်တဲ့အတွက် ဒီ command ကို သုံးလို့မရပါဘူး။")
        return

    if context.args and context.args[0].lower() in ("clear", "remove", "off", "none"):
        save_start_image("")
        await update.message.reply_text("✅ /start image ကို ဖယ်ရှားပြီးပါပြီ။")
        return

    image = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        image = update.message.reply_to_message.photo[-1].file_id
    elif update.message.photo:
        image = update.message.photo[-1].file_id
    elif context.args:
        image = context.args[0]

    if not image:
        current = load_start_image()
        if current:
            await update.message.reply_text(
                "ℹ️ လက်ရှိ /start image ရှိပါတယ်။\n"
                "ပြောင်းချင်ရင် photo ကို reply လုပ်ပြီး `/start_img` သုံးပါ၊ "
                "ဒါမှမဟုတ် `/start_img <image_url_or_file_id>` သုံးပါ။\n"
                "ဖယ်ချင်ရင် `/start_img clear` သုံးပါ။"
            )
        else:
            await update.message.reply_text(
                "ℹ️ /start image မသတ်မှတ်ရသေးပါ။\n"
                "Photo ကို reply လုပ်ပြီး `/start_img` သုံးပါ၊ "
                "ဒါမှမဟုတ် `/start_img <image_url_or_file_id>` သုံးပါ။"
            )
        return

    save_start_image(image)
    await update.message.reply_text("✅ /start image ကို သိမ်းပြီးပါပြီ။")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ သင်ဟာ Admin မဟုတ်တဲ့အတွက် ဒီ command ကို သုံးလို့မရပါဘူး။")
        return
    
    source_message = update.message.reply_to_message
    if not context.args and not source_message:
        await update.message.reply_text(
            "❌ ကြော်ညာမယ့်စာသား ထည့်ပေးပါ။ (ဥပမာ- `/broadcast မင်္ဂလာပါ`)\n"
            "သို့မဟုတ် broadcast လုပ်ချင်တဲ့ message ကို reply လုပ်ပြီး `/broadcast` သုံးပါ။"
        )
        return
    
    msg = " ".join(context.args)
    chat_ids = sorted(set(read_id_file(CHAT_LIST_FILE) + read_id_file(USER_LIST_FILE)))
    if not chat_ids:
        await update.message.reply_text("❌ ပို့စရာ Chat မရှိသေးပါ။")
        return

    progress = await update.message.reply_text(
        f"📢 Broadcast စတင်နေပါပြီ...\nTotal: {len(chat_ids)}\nSent: 0\nFailed: 0"
    )
    sent = 0
    failed = 0
    dead_chats = []

    for index, chat_id in enumerate(chat_ids, start=1):
        try:
            if source_message:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=source_message.chat_id,
                    message_id=source_message.message_id,
                )
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"📢 **ကြော်ညာချက်:**\n\n{msg}", parse_mode='Markdown')
            sent += 1
        except Forbidden:
            failed += 1
            dead_chats.append(chat_id)
            logger.info("Broadcast target %s is no longer reachable", chat_id)
        except Exception:
            failed += 1
            logger.exception("Broadcast failed for chat %s", chat_id)

        if index % 10 == 0 or index == len(chat_ids):
            try:
                await progress.edit_text(
                    "📢 Broadcast လုပ်နေပါတယ်...\n"
                    f"Total: {len(chat_ids)}\n"
                    f"Done: {index}/{len(chat_ids)}\n"
                    f"Sent: {sent}\n"
                    f"Failed: {failed}\n"
                    f"Remaining: {len(chat_ids) - index}"
                )
            except Exception:
                logger.exception("Could not edit broadcast progress message")

        await asyncio.sleep(BROADCAST_DELAY_SECONDS)

    for chat_id in dead_chats:
        remove_chat(chat_id)

    await progress.edit_text(
        "✅ Broadcast ပြီးပါပြီ။\n"
        f"Total: {len(chat_ids)}\n"
        f"Sent: {sent}\n"
        f"Failed: {failed}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')

async def bot_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member_update = update.my_chat_member
    if not member_update:
        return

    chat = member_update.chat
    if chat.type not in GROUP_TYPES:
        return

    new_status = member_update.new_chat_member.status
    if new_status in ("left", "kicked"):
        remove_chat(chat.id)
        if chat.id in games:
            game = games[chat.id]
            if game.phase_task and not game.phase_task.done():
                game.phase_task.cancel()
            del games[chat.id]
        return

    if new_status not in ("member", "administrator"):
        return

    save_chat(chat.id)
    if new_status != "administrator":
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "⚠️ Bot ကို group ထဲထည့်ပြီးပါပြီ၊ ဒါပေမယ့် Admin မဟုတ်သေးပါ။\n"
                "Werewolf game command တွေသုံးဖို့ Bot ကို Admin ပေးထားဖို့လိုပါတယ်။"
            ),
        )
        return

    await context.bot.send_message(
        chat_id=chat.id,
        text="✅ Bot ကို Admin အဖြစ် ထည့်ပြီးပါပြီ။ Werewolf game command တွေ သုံးလို့ရပါပြီ။",
    )

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_game_chat(update, context):
        return

    chat_id = update.effective_chat.id
    if chat_id in games:
        game = games[chat_id]
        await update.message.reply_text(
            "⚠️ ဒီ Group မှာ ဂိမ်းတစ်ခု ရှိနေပြီးသားပါ။\n"
            f"လက်ရှိအခြေအနေ: {describe_game_status(game.status)}\n"
            "ဂိမ်းအသစ်စချင်ရင် အရင် `/end` နဲ့ ရပ်ပါ။"
        )
        return
    games[chat_id] = WerewolfGame(chat_id)
    keyboard = [[InlineKeyboardButton("🙋‍♂️ ဂိမ်းထဲဝင်မည်", callback_data=f"join_{chat_id}")]]
    await update.message.reply_text("🎮 **Werewolf ဂိမ်းအသစ် စတင်ပါပြီ!**\n\nအနည်းဆုံး ၄ ယောက် ရှိမှ `/startgame` နဲ့ စလို့ရပါမယ်။", reply_markup=InlineKeyboardMarkup(keyboard))

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_game_chat(update, context):
        return

    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game:
        await update.message.reply_text("⚠️ Game မရှိသေးပါ။ အရင် `/newgame` သုံးပြီး game အသစ်စပါ။")
        return

    if game.status != "joining":
        await update.message.reply_text(
            "⚠️ ဒီ game ထဲကို join လုပ်လို့မရတော့ပါ။\n"
            f"လက်ရှိအခြေအနေ: {describe_game_status(game.status)}\n"
            "Game အသစ်စချင်ရင် `/end` ပြီးမှ `/newgame` သုံးပါ။"
        )
        return

    user = update.effective_user
    if game.add_player(user.id, user.first_name):
        await update.message.reply_text(f"✅ {user.first_name} ဂိမ်းထဲဝင်ပြီးပါပြီ။")
    else:
        await update.message.reply_text("⚠️ သင် ဂိမ်းထဲဝင်ပြီးသားပါ။")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_game_chat(update, context):
        return

    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("⚠️ စတင်စရာ game မရှိသေးပါ။ အရင် `/newgame` သုံးပါ။")
        return
    game = games[chat_id]
    if len(game.players) < 4:
        await update.message.reply_text(
            f"⚠️ လူမလုံလောက်သေးပါ။ (လက်ရှိ: {len(game.players)} ယောက်)\n"
            "အနည်းဆုံး ၄ ယောက်လိုပါတယ်။ `/join` သို့မဟုတ် Join ခလုတ်နဲ့ ဝင်ခိုင်းပါ။"
        )
        return
    if game.status != "joining":
        await update.message.reply_text(
            "⚠️ ဒီ game ကို စပြီးသားပါ။\n"
            f"လက်ရှိအခြေအနေ: {describe_game_status(game.status)}\n"
            "Game အသစ်စချင်ရင် `/end` ပြီးမှ `/newgame` သုံးပါ။"
        )
        return

    game.status = "starting"
    pids = list(game.players.keys())
    random.shuffle(pids)
    num_wolves = max(1, len(pids) // 4)
    for i in range(num_wolves): game.players[pids[i]]['role'] = 'werewolf'
    game.players[pids[num_wolves]]['role'] = 'seer'
    for i in range(num_wolves + 1, len(pids)): game.players[pids[i]]['role'] = 'villager'
    
    await update.message.reply_text("🎭 **Role တွေကို Private Message ပို့ပေးလိုက်ပါပြီ။ စစ်ဆေးကြည့်ပါ။**")
    blocked_players = []
    for pid, p in game.players.items():
        sent = await send_private_message(
            context,
            pid,
            f"🎭 သင့်ရဲ့ Role ကတော့: **{p['role'].upper()}** ဖြစ်ပါတယ်။",
        )
        if not sent:
            blocked_players.append(p["name"])

    if blocked_players:
        names = ", ".join(blocked_players)
        await update.message.reply_text(
            "⚠️ ဒီကစားသမားတွေကို Private Message ပို့လို့မရပါဘူး။\n"
            f"{names}\n\n"
            "Bot ကို private မှာ `/start` နှိပ်ပြီးမှ game ကိုပြန်စပါ။\n"
            "ဒီ game ကို ရပ်လိုက်ပါပြီ။ `/newgame` နဲ့ ပြန်စပါ။"
        )
        del games[chat_id]
        return
    
    schedule_game_phase(chat_id, start_night(chat_id, context))

async def start_night(chat_id, context):
    if chat_id not in games: return
    game = games[chat_id]
    game.status = "night"
    game.night_kills = {}
    await context.bot.send_message(chat_id=chat_id, text="🌑 **ညရောက်ပါပြီ... ရွာသားတွေ အိပ်ပျော်နေကြပါတယ်။**\nဝံပုလွေတွေနဲ့ Seer တို့ အလုပ်လုပ်နေကြပါတယ်။ (၃ မိနစ် စောင့်ပါ)")
    
    alive = game.get_alive_players()
    blocked_players = []
    for pid, p in alive.items():
        if p['role'] == 'werewolf':
            kb = [[InlineKeyboardButton(p2['name'], callback_data=f"kill_{chat_id}_{uid2}")] for uid2, p2 in alive.items() if p2['role'] != 'werewolf']
            sent = await send_private_message(
                context,
                pid,
                "🐺 **ဘယ်သူ့ကို သတ်မလဲ?**",
                reply_markup=InlineKeyboardMarkup(kb),
            )
            if not sent:
                blocked_players.append(p["name"])
        elif p['role'] == 'seer':
            kb = [[InlineKeyboardButton(p2['name'], callback_data=f"check_{chat_id}_{uid2}")] for uid2, p2 in alive.items() if uid2 != pid]
            sent = await send_private_message(
                context,
                pid,
                "🔮 **ဘယ်သူ့ကို စစ်ဆေးမလဲ?**",
                reply_markup=InlineKeyboardMarkup(kb),
            )
            if not sent:
                blocked_players.append(p["name"])

    if blocked_players:
        names = ", ".join(blocked_players)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ Private action ပို့လို့မရတဲ့ ကစားသမားရှိပါတယ်။\n"
                f"{names}\n\n"
                "သူတို့ Bot ကို private မှာ `/start` နှိပ်ထားဖို့လိုပါတယ်။"
            ),
        )
    
    await asyncio.sleep(180)
    await start_day(chat_id, context)

async def start_day(chat_id, context):
    if chat_id not in games: return
    game = games[chat_id]
    game.status = "day"
    
    victim_id = None
    if game.night_kills:
        victim_id = max(game.night_kills, key=game.night_kills.get)
        game.players[victim_id]['alive'] = False
        await context.bot.send_message(chat_id=chat_id, text=f"☀️ **မနက်လင်းပါပြီ!**\n😱 မနေ့ညက **{game.players[victim_id]['name']}** အသတ်ခံလိုက်ရပါတယ်။")
    else:
        await context.bot.send_message(chat_id=chat_id, text="☀️ **မနက်လင်းပါပြီ!**\n🙏 မနေ့ညက ဘယ်သူမှ အသတ်မခံရပါဘူး။")

    winner = game.check_winner()
    if winner:
        await end_game(chat_id, context, winner)
        return

    game.status = "voting"
    game.day_votes = {}
    game.voted_users = set()
    alive = game.get_alive_players()
    kb = [[InlineKeyboardButton(p['name'], callback_data=f"vote_{chat_id}_{uid}")] for uid, p in alive.items()]
    await context.bot.send_message(chat_id=chat_id, text="⚖️ **ဝံပုလွေလို့ သံသယရှိသူကို မဲပေးကြပါ။ (၃ မိနစ်)**", reply_markup=InlineKeyboardMarkup(kb))
    
    await asyncio.sleep(180)
    await process_voting(chat_id, context)

async def process_voting(chat_id, context):
    if chat_id not in games: return
    game = games[chat_id]
    if game.status != "voting": return

    if game.day_votes:
        lynched_id = max(game.day_votes, key=game.day_votes.get)
        game.players[lynched_id]['alive'] = False
        role = game.players[lynched_id]['role']
        await context.bot.send_message(chat_id=chat_id, text=f"⚖️ မဲအများဆုံးရတဲ့ **{game.players[lynched_id]['name']}** ကို ဖမ်းဆီးလိုက်ပါပြီ။\nသူ့ရဲ့ Role က **{role.upper()}** ဖြစ်ပါတယ်။")
    else:
        await context.bot.send_message(chat_id=chat_id, text="⚖️ ဘယ်သူမှ မဲမပေးကြတဲ့အတွက် ဒီနေ့ ဘယ်သူ့ကိုမှ မဖမ်းပါဘူး။")

    winner = game.check_winner()
    if winner:
        await end_game(chat_id, context, winner)
    else:
        await start_night(chat_id, context)

async def end_game(chat_id, context, winner):
    game = games[chat_id]
    current_task = asyncio.current_task()
    if game.phase_task and game.phase_task is not current_task and not game.phase_task.done():
        game.phase_task.cancel()

    msg = "🎉 **ဂိမ်းပြီးဆုံးပါပြီ!**\n\n"
    if winner == "villagers":
        msg += "🏆 **ရွာသားများ အောင်နိုင်သွားပါပြီ!**"
    elif winner == "werewolves":
        msg += "🏆 **ဝံပုလွေများ အောင်နိုင်သွားပါပြီ!**"
    else:
        msg += "🛑 **Admin က game ကို ရပ်လိုက်ပါပြီ။**"

    roles_summary = "\n".join([f"- {p['name']}: {(p['role'] or 'unknown').upper()}" for p in game.players.values()])
    await context.bot.send_message(chat_id=chat_id, text=f"{msg}\n\n**Roles:**\n{roles_summary}")
    del games[chat_id]

async def end_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_game_chat(update, context):
        return

    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("⚠️ ရပ်စရာ game မရှိပါ။ Game စချင်ရင် `/newgame` သုံးပါ။")
        return

    await end_game(chat_id, context, "manual")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith("join_"):
        cid = int(data.split("_")[1])
        if not await is_game_group_allowed(context, cid):
            await query.answer("⚠️ Bot ကို group admin ပေးထားဖို့လိုပါတယ်။")
            return
        game = games.get(cid)
        if not game:
            await query.answer("⚠️ Game မရှိတော့ပါ။ /newgame နဲ့ ပြန်စပါ။")
            return
        if game.status != "joining":
            await query.answer(f"⚠️ Join မရတော့ပါ။ ({describe_game_status(game.status)})")
            return
        if game.add_player(user_id, query.from_user.first_name):
            await query.answer("✅ ဝင်လိုက်ပါပြီ")
            alive = game.players
            await query.edit_message_text(f"🎮 **Werewolf ဂိမ်း**\nကစားသမား: {len(alive)} ယောက်\n" + "\n".join([f"- {p['name']}" for p in alive.values()]), reply_markup=query.message.reply_markup)
        else:
            await query.answer("⚠️ သင် ဂိမ်းထဲဝင်ပြီးသားပါ။")
    
    elif data.startswith("kill_"):
        _, cid, victim_id = data.split("_")
        cid, victim_id = int(cid), int(victim_id)
        if not await is_game_group_allowed(context, cid):
            await query.answer("⚠️ Bot ကို group admin ပေးထားဖို့လိုပါတယ်။")
            return
        game = games.get(cid)
        if not game:
            await query.answer("⚠️ Game မရှိတော့ပါ။")
            return
        if victim_id not in game.players:
            await query.answer("⚠️ ဒီကစားသမားကို မတွေ့တော့ပါ။")
            return
        if game.status == "night":
            game.night_kills[victim_id] = game.night_kills.get(victim_id, 0) + 1
            await query.answer("🐺 သတ်ဖို့ ရွေးချယ်လိုက်ပါပြီ")
            await query.edit_message_text("🐺 သတ်ဖို့ ရွေးချယ်ပြီးပါပြီ။ ညကုန်ဆုံးတာကို စောင့်ပါ။")
        else:
            await query.answer(f"⚠️ အခုညအချိန်မဟုတ်ပါ။ ({describe_game_status(game.status)})")

    elif data.startswith("check_"):
        _, cid, target_id = data.split("_")
        cid, target_id = int(cid), int(target_id)
        if not await is_game_group_allowed(context, cid):
            await query.answer("⚠️ Bot ကို group admin ပေးထားဖို့လိုပါတယ်။")
            return
        game = games.get(cid)
        if not game:
            await query.answer("⚠️ Game မရှိတော့ပါ။")
            return
        if target_id not in game.players:
            await query.answer("⚠️ ဒီကစားသမားကို မတွေ့တော့ပါ။")
            return
        if game.status == "night":
            role = game.players[target_id]['role']
            await query.answer("🔮 စစ်ဆေးပြီးပါပြီ")
            await query.edit_message_text(f"🔮 **{game.players[target_id]['name']}** ရဲ့ Role ကတော့ **{role.upper()}** ဖြစ်ပါတယ်။")
        else:
            await query.answer(f"⚠️ အခုညအချိန်မဟုတ်ပါ။ ({describe_game_status(game.status)})")

    elif data.startswith("vote_"):
        _, cid, victim_id = data.split("_")
        cid, victim_id = int(cid), int(victim_id)
        if not await is_game_group_allowed(context, cid):
            await query.answer("⚠️ Bot ကို group admin ပေးထားဖို့လိုပါတယ်။")
            return
        game = games.get(cid)
        if not game:
            await query.answer("⚠️ Game မရှိတော့ပါ။")
            return
        if victim_id not in game.players:
            await query.answer("⚠️ ဒီကစားသမားကို မတွေ့တော့ပါ။")
            return
        if game.status != "voting":
            await query.answer(f"⚠️ မဲပေးချိန်မဟုတ်ပါ။ ({describe_game_status(game.status)})")
            return
        if user_id in game.voted_users:
            await query.answer("⚠️ သင် မဲပေးပြီးသားပါ။")
            return

        if game.status == "voting":
            game.day_votes[victim_id] = game.day_votes.get(victim_id, 0) + 1
            game.voted_users.add(user_id)
            await query.answer("⚖️ မဲပေးပြီးပါပြီ")
            await context.bot.send_message(chat_id=cid, text=f"🗳 **{query.from_user.first_name}** က မဲပေးလိုက်ပါပြီ။")
    
    elif data == "show_help":
        await query.answer()
        await context.bot.send_message(chat_id=user_id, text=HELP_TEXT, parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(
        "Unhandled telegram update error. update=%r",
        update,
        exc_info=(type(error), error, error.__traceback__) if error else None,
    )

async def set_bot_commands(app):
    commands = [
        BotCommand("start", "Open bot menu"),
        BotCommand("help", "Show game rules"),
        BotCommand("newgame", "Start a new group game"),
        BotCommand("join", "Join the current game"),
        BotCommand("startgame", "Begin the current game"),
        BotCommand("end", "End the current game"),
        BotCommand("broadcast", "Admin: broadcast to chats"),
        BotCommand("start_img", "Admin: set or clear /start image"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Telegram command menu registered")

async def main():
    while True:
        try:
            app = (
                ApplicationBuilder()
                .token(TOKEN)
                .connect_timeout(30)
                .read_timeout(30)
                .write_timeout(30)
                .pool_timeout(30)
                .concurrent_updates(True)
                .build()
            )
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("start_img", start_img))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(CommandHandler("broadcast", broadcast))
            app.add_handler(CommandHandler("newgame", new_game))
            app.add_handler(CommandHandler("join", join_game))
            app.add_handler(CommandHandler("startgame", start_game))
            app.add_handler(CommandHandler("end", end_game_command))
            app.add_handler(ChatMemberHandler(bot_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
            app.add_handler(CallbackQueryHandler(button_handler))
            app.add_error_handler(error_handler)
            
            logger.info("Bot starting...")
            await app.initialize()
            await set_bot_commands(app)
            await app.start()
            await app.updater.start_polling()
            
            # Keep the bot running
            while True:
                await asyncio.sleep(3600)
                
        except Exception:
            logger.exception("Bot crashed")
            await asyncio.sleep(10) # Wait before retry

if __name__ == '__main__':
    asyncio.run(main())
