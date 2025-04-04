import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler
import re
import json
import requests
from bs4 import BeautifulSoup

# توکن بات
TOKEN = "7695882385:AAEulsrRvfQU562jTbNkujsiA-HP6LBTNbU"

# آیدی کانال (به صورت عددی)
CHANNEL_ID = "-1002616936079"

# Chat ID ادمین 
ADMIN_CHAT_ID = "1451384311"

# تابع برای دریافت قیمت به‌روز طلا از سایت
def get_gold_price():
    url = "https://www.tgju.org/profile/geram18"  # لینک صفحه قیمت طلا 18 عیار
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        price_tag = soup.find("span", {"data-col": "info.last_trade.PDrCotVal"})
        if price_tag:
            price_str = price_tag.text.strip().replace(",", "")
            return int(price_str), None
        else:
            return None, "قیمت طلا پیدا نشد!"
    
    except requests.exceptions.RequestException as e:
        return None, f"خطا در دریافت قیمت: {e}"

# تابع برای استخراج اطلاعات از توضیحات پست
def extract_product_info(caption):
    print(f"Extracting info from caption: {caption}")
    if not caption:
        print("No caption found!")
        return None
    
    lines = caption.split('\n')
    name = lines[0].strip() if lines else "محصول ناشناخته"
    print(f"Product name: {name}")
    
    weight = re.search(r'وزن:\s*([\d.]+)\s*گرم', caption)
    ajrat = re.search(r'اجرت:\s*([\d.]+)%', caption)
    profit = re.search(r'سود:\s*([\d.]+)%', caption)
    
    weight = float(weight.group(1)) if weight else 0
    ajrat = float(ajrat.group(1)) if ajrat else 0
    profit = float(profit.group(1)) if profit else 0
    
    print(f"Extracted - Weight: {weight}, Ajrat: {ajrat}, Profit: {profit}")
    
    return {
        "name": name,
        "weight": weight,
        "ajrat": ajrat,
        "profit": profit
    }

# تابع برای محاسبه قیمت
def calculate_price(weight, ajrat, profit, price_per_gram):
    base_price = weight * price_per_gram
    ajrat_amount = base_price * (ajrat / 100)
    profit_amount = base_price * (profit / 100)
    total_price = base_price + ajrat_amount + profit_amount
    return int(total_price)

# تابع برای مدیریت پست‌های جدید
async def handle_new_post(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("New post detected!")
    message = update.channel_post
    
    print(f"Chat ID: {message.chat_id}, Expected: {CHANNEL_ID}")
    if str(message.chat_id) != CHANNEL_ID:
        print("Chat ID does not match!")
        return
    
    caption = message.caption if message.caption else ""
    print(f"Caption: {caption}")
    
    product_info = extract_product_info(caption)
    if not product_info or product_info["weight"] == 0:
        print("Product info incomplete or weight is 0!")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="لطفاً اطلاعات محصول رو به این شکل وارد کنید:\n"
                     "نام محصول\nوزن: (عدد و برای ممیز نقطه) گرم\nاجرت: (عدد)%\nسود: (عدد)%"
            )
        except Exception as e:
            print(f"Error sending message to admin: {e}")
        return
    
    product_data = {
        "weight": product_info["weight"],
        "ajrat": product_info["ajrat"],
        "profit": product_info["profit"]
    }
    product_data_json = json.dumps(product_data)
    
    keyboard = [
        [InlineKeyboardButton("محاسبه قیمت آنلاین", callback_data=f'calculate_price|{product_data_json}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # ویرایش پست برای اضافه کردن دکمه
    try:
        await context.bot.edit_message_caption(
            chat_id=message.chat_id,
            message_id=message.message_id,
            caption=message.caption + "\n\nبرای مشاهده قیمت به‌روز، روی دکمه زیر کلیک کنید:",
            reply_markup=reply_markup
        )
        print("Post edited successfully!")
    except Exception as e:
        print(f"Error editing post: {e}")

# تابع برای مدیریت کلیک روی دکمه
async def button_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    callback_data = query.data.split('|', 1)
    if len(callback_data) != 2 or callback_data[0] != 'calculate_price':
        await query.answer("خطا: داده‌های نامعتبر!", show_alert=True)
        return
    
    try:
        product_data = json.loads(callback_data[1])
    except json.JSONDecodeError:
        await query.answer("خطا: اطلاعات محصول نامعتبر است!", show_alert=True)
        return
    
    price_per_gram, error = get_gold_price()
    if price_per_gram is None:
        await query.answer(f"خطا: {error}", show_alert=True)
        return
    
    total_price = calculate_price(
        product_data['weight'],
        product_data['ajrat'],
        product_data['profit'],
        price_per_gram
    )
    
    # نمایش قیمت در پاپ‌آپ
    message = (
        f"قیمت کل: {total_price // 10 :,} تومان\n"
        f"قیمت فعلی طلا (هر گرم): {price_per_gram // 10 :,} تومان"
    )
    await query.answer(message, show_alert=True)

application = Application.builder().token(TOKEN).build()

application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_new_post))
application.add_handler(CallbackQueryHandler(button_callback))

print("Starting bot...")
application.run_polling()