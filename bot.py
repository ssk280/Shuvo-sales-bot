from datetime import datetime
import logging
import os
sqlite3
import pytz
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Constants
ADMIN_ID = 6602778994
DB_NAME = "sales_manager.db"
TZ = pytz.timezone("Asia/Dhaka")

# Conversation states for Product Sale
NAME, PURCHASE_PRICE, SELLING_PRICE = range(3)


# Database Initialization
def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            profit REAL NOT NULL,
            sale_date TEXT NOT NULL,
            sale_timestamp TEXT NOT NULL
        )
    """)
  conn.commit()
  conn.close()


# Admin Security Check Decorator
def admin_only(func):
  async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
      await update.message.reply_text(
          "⚠️ আপনার এই বট ব্যবহারের অনুমতি নেই।"
      )
      return
    return await func(update, context)

  return wrapper


# Main Menu Keyboard
def get_main_keyboard():
  keyboard = [
      [
          KeyboardButton("🛒 একটি প্রোডাক্ট সেল হলো"),
          KeyboardButton("📦 মোট প্রোডাক্ট সেল"),
      ],
      [KeyboardButton("💰 মোট লাভ"), KeyboardButton("📊 মোট সেল")],
      [KeyboardButton("📅 বিক্রির হিস্ট্রি"), KeyboardButton("🔄 রিসেট")],
  ]
  return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# /start Command
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  welcome_text = (
      "👋 স্বাগতম Shuvo Sales Manager Bot-এ!\nআপনার ব্যবসার হিসাব-নিকাশ পরিচালনা"
      " করতে নিচের বাটনগুলো ব্যবহার করুন।"
  )
  await update.message.reply_text(
      welcome_text, reply_markup=get_main_keyboard()
  )


# --- Product Sale Conversation ---
@admin_only
async def start_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "🛒 প্রোডাক্টের নাম লিখুন (যেমন: T-Shirt):",
      reply_markup=ReplyKeyboardRemove(),
  )
  return NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
  context.user_data["product_name"] = update.message.text.strip()
  await update.message.reply_text("💵 Purchase Price (ক্রয়মূল্য কত টাকা?):")
  return PURCHASE_PRICE


async def receive_purchase_price(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  try:
    purchase_price = float(update.message.text.strip())
    context.user_data["purchase_price"] = purchase_price
    await update.message.reply_text("💰 Selling Price (বিক্রয়মূল্য কত টাকা?):")
    return SELLING_PRICE
  except ValueError:
    await update.message.reply_text(
        "⚠️ দয়া করে সঠিক সংখ্যা (সংখ্যায়) ক্রয়মূল্য লিখুন:"
    )
    return PURCHASE_PRICE


async def receive_selling_price(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  try:
    selling_price = float(update.message.text.strip())
    purchase_price = context.user_data["purchase_price"]
    product_name = context.user_data["product_name"]

    profit = selling_price - purchase_price
    now_dhaka = datetime.now(TZ)
    sale_date = now_dhaka.strftime("%Y-%m-%d")
    sale_timestamp = now_dhaka.strftime("%Y-%m-%d %H:%M:%S")

    # Save to Database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO sales (product_name, purchase_price, selling_price, profit, sale_date, sale_timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            product_name,
            purchase_price,
            selling_price,
            profit,
            sale_date,
            sale_timestamp,
        ),
    )
    conn.commit()
    conn.close()

    result_text = (
        f"✅ **প্রোডাক্ট সেল সফলভাবে সংরক্ষিত হয়েছে!**\n\n"
        f"📌 প্রোডাক্ট: {product_name}\n"
        f"🔹 Purchase: {purchase_price:,.0f}৳\n"
        f"🔸 Sale: {selling_price:,.0f}৳\n"
        f"📈 Profit: {profit:,.0f}৳\n"
        f"📅 তারিখ: {sale_date}"
    )

    await update.message.reply_text(
        result_text, parse_mode="Markdown", reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END
  except ValueError:
    await update.message.reply_text(
        "⚠️ দয়া করে সঠিক সংখ্যা (সংখ্যায়) বিক্রয়মূল্য লিখুন:"
    )
    return SELLING_PRICE


async def cancel_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text(
      "❌ সেল এন্ট্রি বাতিল করা হয়েছে।", reply_markup=get_main_keyboard()
  )
  return ConversationHandler.END


# --- Statistics Handlers ---
@admin_only
async def total_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT COUNT(*) FROM sales")
  count = cursor.fetchone()[0]
  conn.close()

  await update.message.reply_text(
      f"📦 **মোট প্রোডাক্ট সেল:** {count} টি", parse_mode="Markdown"
  )


@admin_only
async def total_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT SUM(profit) FROM sales")
  profit = cursor.fetchone()[0]
  conn.close()

  total_p = profit if profit else 0
  await update.message.reply_text(
      f"💰 **মোট লাভ:** {total_p:,.0f}৳", parse_mode="Markdown"
  )


@admin_only
async def total_sales(update: Update, context: ContextTypes.DEFAULT_TYPE):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("SELECT SUM(selling_price) FROM sales")
  sales = cursor.fetchone()[0]
  conn.close()

  total_s = sales if sales else 0
  await update.message.reply_text(
      f"📊 **মোট সেল:** {total_s:,.0f}৳", parse_mode="Markdown"
  )


# --- Sales History Handler ---
@admin_only
async def sales_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT DISTINCT sale_date FROM sales ORDER BY sale_date DESC"
  )
  dates = cursor.fetchall()

  if not dates:
    await update.message.reply_text("📭 কোনো বিক্রির হিস্ট্রি পাওয়া যায়নি।")
    conn.close()
    return

  response = "📅 **বিক্রির হিস্ট্রি (তারিখ অনুযায়ী):**\n\n"

  for (date_str,) in dates:
    # Format date nicely
    formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime(
        "%d %B %Y"
    )
    response += f"🗓 **{formatted_date}**\n"

    cursor.execute(
        """
            SELECT product_name, purchase_price, selling_price, profit 
            FROM sales WHERE sale_date = ?
        """,
        (date_str,),
    )
    items = cursor.fetchall()

    day_products = len(items)
    day_sales = 0
    day_profit = 0

    for idx, item in enumerate(items, 1):
      p_name, pur, sel, prof = item
      day_sales += sel
      day_profit += prof
      response += (
          f"  {idx}. {p_name} | Purchase: {pur:,.0f}৳ | Sale: {sel:,.0f}৳ |"
          f" Profit: {prof:,.0f}৳\n"
      )

    response += f"\n  🔹 **Daily Summary:** Products: {day_products} | Sales: {day_sales:,.0f}৳ | Profit: {day_profit:,.0f}৳\n"
    response += "-----------------------------------\n"

  conn.close()

  # Send message in chunks if too long
  if len(response) > 4000:
    for i in range(0, len(response), 4000):
      await update.message.reply_text(
          response[i : i + 4000], parse_mode="Markdown"
      )
  else:
    await update.message.reply_text(response, parse_mode="Markdown")


# --- Reset System ---
@admin_only
async def reset_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [InlineKeyboardButton("📜 History Reset", callback_data="reset_history")],
      [
          InlineKeyboardButton(
              "📅 Today's Calculation Reset", callback_data="reset_today"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text(
      "🔄 আপনি কোন ডেটা রিসেট করতে চান?", reply_markup=reply_markup
  )


async def reset_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.callback_query
  await query.answer()
  data = query.data

  if data == "reset_history":
    keyboard = [
        [
            InlineKeyboardButton("✅ হ্যাঁ", callback_data="confirm_hist_yes"),
            InlineKeyboardButton("❌ না", callback_data="confirm_hist_no"),
        ]
    ]
    await query.edit_message_text(
        "⚠️ আপনি কি নিশ্চিত যে সব দিনের বিক্রির History Delete করতে চান?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
  elif data == "reset_today":
    keyboard = [
        [
            InlineKeyboardButton("✅ হ্যাঁ", callback_data="confirm_today_yes"),
            InlineKeyboardButton("❌ না", callback_data="confirm_today_no"),
        ]
    ]
    await query.edit_message_text(
        "⚠️ আপনি কি নিশ্চিত যে শুধু আজকের বিক্রির হিসাব Delete করতে চান?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

  elif data == "confirm_hist_yes":
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales")
    conn.commit()
    conn.close()
    await query.edit_message_text(
        "✅ সফলভাবে সব হিস্ট্রি রিসেট করা হয়েছে।"
    )

  elif data == "confirm_hist_no":
    await query.edit_message_text(
        "❌ হিস্ট্রি রিসেট বাতিল করা হয়েছে।"
    )

  elif data == "confirm_today_yes":
    now_dhaka = datetime.now(TZ).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE sale_date = ?", (now_dhaka,))
    conn.commit()
    conn.close()
    await query.edit_message_text(
        "✅ সফলভাবে আজকের বিক্রির হিসাব রিসেট করা হয়েছে।"
    )

  elif data == "confirm_today_no":
    await query.edit_message_text(
        "❌ আজকের হিসাব রিসেট বাতিল করা হয়েছে।"
    )


# Main function
def main():
  init_db()

  token = os.getenv("9066884590:AAHjEAm2s0abK6Ik0EXZfB4v6EYsILJw9rM")
  if not token:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
    return

  application = Application.builder().token(token).build()

  # Conversation handler for product sale
  sale_conv_handler = ConversationHandler(
      entry_points=[
          MessageHandler(
              filters.Regex("^🛒 একটি প্রোডাক্ট সেল হলো$"), start_sale
          )
      ],
      states={
          NAME: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_name
              )
          ],
          PURCHASE_PRICE: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_purchase_price
              )
          ],
          SELLING_PRICE: [
              MessageHandler(
                  filters.TEXT & ~filters.COMMAND, receive_selling_price
              )
          ],
      },
      fallbacks=[CommandHandler("cancel", cancel_sale)],
  )

  # Handlers
  application.add_handler(CommandHandler("start", start))
  application.add_handler(sale_conv_handler)
  application.add_handler(
      MessageHandler(
          filters.Regex("^📦 মোট প্রোডাক্ট সেল$"), total_products
      )
  )
  application.add_handler(
      MessageHandler(filters.Regex("^💰 মোট লাভ$"), total_profit)
  )
  application.add_handler(
      MessageHandler(filters.Regex("^📊 মোট সেল$"), total_sales)
  )
  application.add_handler(
      MessageHandler(filters.Regex("^📅 বিক্রির হিস্ট্রি$"), sales_history)
  )
  application.add_handler(MessageHandler(filters.Regex("^🔄 রিসেট$"), reset_menu))
  application.add_handler(CallbackQueryHandler(reset_callback_handler))

  # Start Bot
  logger.info("Shuvo Sales Manager Bot is starting...")
  application.run_polling()


if __name__ == "__main__":
  main()
