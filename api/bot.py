import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, InputFile
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import telegram
import sqlite3
import json
import uuid
import random
import asyncio


# Logging configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
def init_db():
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    # Add table for companies
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    owner_id INTEGER,
                    value REAL DEFAULT 10000.0,
                    profit_margin REAL DEFAULT 0.1,
                    team INTEGER DEFAULT 1,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                )''')
    # Add table for company members
    c.execute('''CREATE TABLE IF NOT EXISTS company_members (
                    company_id INTEGER,
                    user_id INTEGER,
                    role TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (company_id) REFERENCES companies(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    PRIMARY KEY (company_id, user_id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 1000.0,
                    portfolio TEXT DEFAULT '{}',
                    invite_link TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    product_id INTEGER,
                    amount INTEGER,
                    price REAL,
                    date TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS market (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    current_price REAL,
                    availability INTEGER
                )''')
    # Add sample products to the market
    products = [
        (1, 'Gold', 1500.0, 1000),
        (2, 'Silver', 25.0, 5000),
        (3, 'Platinum', 900.0, 500),
        (4, 'Palladium', 2300.0, 300),
        (5, 'Oil', 70.0, 10000),
        (6, 'Copper', 4.0, 8000)
    ]
    c.executemany("INSERT OR IGNORE INTO market (id, name, current_price, availability) VALUES (?, ?, ?, ?)", products)
    conn.commit()
    conn.close()

# List of adjectives, names, and Roman numerals for generating random usernames
adjectives = [
    "Furious", "Brave", "Cunning", "Wise", "Swift", "Mighty", "Bold", "Fearless", "Valiant", "Noble",
    "Gallant", "Heroic", "Loyal", "Vigilant", "Resolute", "Tenacious", "Steadfast", "Courageous", "Daring", "Fierce",
    "Adventurous", "Ambitious", "Charming", "Determined", "Dynamic", "Energetic", "Enthusiastic", "Passionate", "Resourceful", "Vibrant"
]

names = [
    "Mark", "Anna", "John", "Alice", "Tom", "Laura", "James", "Linda", "Robert", "Mary",
    "Michael", "Patricia", "William", "Barbara", "David", "Susan", "Richard", "Margaret", "Joseph", "Lisa",
    "Charles", "Karen", "Christopher", "Betty", "Daniel", "Helen", "Paul", "Sandra", "Steven", "Donna"
]

roman_numerals = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX"
]

# Function to generate a random username
def generate_random_username():
    while True:
        base_username = f"{random.choice(adjectives)} {random.choice(names)}"
        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE username LIKE ?", (f"{base_username}%",))
        count = c.fetchone()[0]
        conn.close()
        if count == 0:
            return base_username
        else:
            base_username = f"{base_username} {roman_numerals[count % len(roman_numerals)]}"
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users WHERE username = ?", (base_username,))
            if c.fetchone()[0] == 0:
                return base_username

# Function to generate a unique invite link
def generate_invite_link(user_id):
    unique_id = str(uuid.uuid4())[:8]  # Generate unique ID and shorten to 8 characters
    return f"https://t.me/WolfsofTonStreet_bot?start={unique_id}"

# Function to calculate user's total wealth
def calculate_wealth(user_id):
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT balance, portfolio FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    balance = user_data[0]
    portfolio = json.loads(user_data[1])
    total_value = balance

    for product_id, quantity in portfolio.items():
        c.execute("SELECT current_price FROM market WHERE id = ?", (product_id,))
        product_price = c.fetchone()[0]
        total_value += product_price * quantity

    conn.close()
    return total_value, balance

# Function to display the menu with buttons
async def menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    total_wealth, balance = calculate_wealth(user_id)

    intro_text = (
        f"Welcome to the Wolfs of Ton Street game! 🎉\n\n"
        f"Your total wealth: {total_wealth:.2f} units\n"
        f"Your balance: {balance:.2f} units\n\n"
        "Game rules are simple:\n"
        "1. You start with a balance of 1000 units.\n"
        "2. You can buy and sell various products available on the market.\n"
        "3. Product prices may change due to random economic events.\n"
        "4. Your goal is to increase your wealth through wise investments.\n"
        "5. Receive 1000 units for each referral through /referral.\n\n"
        "To know more, use /how_to_play\n\n"
        "Choose one of the options below to start:"
    )

    keyboard = [
        [InlineKeyboardButton("Buy product", callback_data='show_market')],
        [InlineKeyboardButton("Market", callback_data='market')],
        [InlineKeyboardButton("Portfolio", callback_data='portfolio')],
        [InlineKeyboardButton("Create Company", callback_data='create_company')],
        [InlineKeyboardButton("Web App", web_app=WebAppInfo(url="https://wolfsonton.netlify.app/"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(intro_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(intro_text, reply_markup=reply_markup)

# Function to handle the /start command with buttons
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username

    if not username:
        username = generate_random_username()

    args = context.args
    invite_id = args[0] if args else None

    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Check if the user already exists
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    user_exists = c.fetchone()

    if not user_exists:
        invite_link = generate_invite_link(user_id)
        c.execute("INSERT INTO users (id, username, invite_link) VALUES (?, ?, ?)", (user_id, username, invite_link))

        if invite_id:
            # Find the inviting user and update their balance
            c.execute("SELECT id FROM users WHERE invite_link LIKE ?", (f"%{invite_id}",))
            inviter = c.fetchone()
            if inviter:
                inviter_id = inviter[0]
                c.execute("UPDATE users SET balance = balance + 1000 WHERE id = ?", (inviter_id,))
                await update.message.reply_text(f"You were invited by user with ID {inviter_id}. They receive 1000 units for the invitation!")

                # Send notification to the inviting user
                await context.bot.send_message(chat_id=inviter_id, text=f"User {username} has joined the game using your invite link! You receive 1000 units.")

        conn.commit()



    conn.close()

    await menu(update, context)
    if not user_exists:
        photo_url = 'https://wolfsonton.com/files/welcome_pic.png'  # Replace with your image URL
        await context.bot.send_photo(chat_id=update.message.chat_id, photo=photo_url, caption=f"Your invite link: {invite_link}")


# Funkcja obsługująca komendę /how_to_play
async def how_to_play(update: Update, context: CallbackContext) -> None:
    
    # photo_url = 'https://wolfsonton.com/files/instruction_pic.png'  # Wstaw ścieżkę do swojego zdjęcia
    # web_link2 = "https://telegra.ph/How-To-Play-in-The-Wolfs-of-Ton-Street-Game-08-08"  # Wstaw tutaj adres URL obsługiwany przez Instant View
    # keyboard = [[InlineKeyboardButton("❓ How to use?", web_app={'url': web_link2})]]
    # reply_markup = InlineKeyboardMarkup(keyboard)

    # # Wysyłanie wiadomości ze zdjęciem i przyciskiem
    # await context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url, caption="To learn how to play, click here:", reply_markup=reply_markup)

    # Tekst, który ma zostać wysłany
    message = "https://telegra.ph/How-To-Play-in-The-Wolfs-of-Ton-Street-Game-08-08\n\n Read this article to learn how to play:"

    # Wysyłanie wiadomości tekstowej
    await update.message.reply_text(message)


# Function to handle the /referral command displaying the user's invite link
async def referral(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT invite_link FROM users WHERE id = ?", (user_id,))
    invite_link = c.fetchone()
    conn.close()

    if invite_link:
        photo_url = 'https://wolfsonton.com/files/referral_pic.png'  # Replace with your image URL
        await context.bot.send_photo(chat_id=update.message.chat_id, photo=photo_url, caption=f"Your invite link: {invite_link[0]}")
    else:
        await update.message.reply_text("Invite link not found.")

# Function to handle the /ranking command displaying the user ranking
async def ranking(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id, username FROM users")
    users = c.fetchall()

    user_wealth = []
    for user in users:
        user_id, username = user
        wealth, _ = calculate_wealth(user_id)
        user_wealth.append((username, wealth))

    user_wealth.sort(key=lambda x: x[1], reverse=True)
    ranking_text = "User ranking:\n"
    for i, (username, wealth) in enumerate(user_wealth, start=1):
        ranking_text += f"{i}. {username}: {wealth:.2f} units\n"

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(ranking_text, reply_markup=reply_markup)
    conn.close()

# Handler to handle callback queries from buttons
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('buy_'):
        _, product_id = data.split('_')
        await buy(update, context, product_id)
    elif data.startswith('sell_'):
        _, product_id = data.split('_')
        await sell(update, context, product_id)
    elif data == 'market':
        await market(update, context)
    elif data == 'portfolio':
        await portfolio(update, context)
    elif data == 'show_market':
        await show_market(update, context)
    elif data == 'menu':
        await menu(update, context)
    elif data == 'company_members':
        await show_company_members(update, context)

# Function to display the market
async def market(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id, name, current_price, availability FROM market")
    products = c.fetchall()
    message_text = 'Available products on the market:\n' + '\n'.join([f'ID: {product[0]}, Name: {product[1]}, Price: {product[2]}, Availability: {product[3]}' for product in products])
    keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
    conn.close()

# Function to display products on the market with purchase buttons
async def show_market(update: Update, context: CallbackContext) -> None:
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id, name, current_price, availability FROM market")
    products = c.fetchall()
    conn.close()

    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(f'Buy {product[1]} - {product[2]}', callback_data=f'buy_{product[0]}')])
    keyboard.append([InlineKeyboardButton("Back to menu", callback_data='menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text('Choose a product to buy:', reply_markup=reply_markup)

# Function to handle product purchase
async def buy(update: Update, context: CallbackContext, product_id) -> None:
    user_id = update.callback_query.from_user.id
    quantity = 1  # Can be adjusted if we want to allow purchasing more than one unit at a time

    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT current_price, availability FROM market WHERE id = ?", (product_id,))
    product = c.fetchone()

    if not product:
        await update.callback_query.message.reply_text('Product does not exist.')
        conn.close()
        return

    total_cost = product[0] * quantity

    if quantity > product[1]:
        await update.callback_query.message.reply_text('Not enough product available on the market.')
        conn.close()
        return

    c.execute("SELECT balance, portfolio FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()

    if user_data is None:
        await update.callback_query.message.reply_text('User not found.')
        conn.close()
        return

    balance = user_data[0]
    portfolio = json.loads(user_data[1])

    if balance < total_cost:
        await update.callback_query.message.reply_text('Insufficient funds.')
        conn.close()
        return

    # Update data
    c.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total_cost, user_id))
    c.execute("UPDATE market SET availability = availability - ? WHERE id = ?", (quantity, product_id))

    # Update portfolio
    if str(product_id) in portfolio:
        portfolio[str(product_id)] += quantity
    else:
        portfolio[str(product_id)] = quantity

    c.execute("UPDATE users SET portfolio = ? WHERE id = ?", (json.dumps(portfolio), user_id))
    c.execute("INSERT INTO transactions (user_id, type, product_id, amount, price, date) VALUES (?, 'buy', ?, ?, ?, datetime('now'))", (user_id, product_id, quantity, product[0]))
    conn.commit()
    conn.close()

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(f'You bought {quantity} units of the product for {total_cost}.', reply_markup=reply_markup)

# Function to handle product sale
async def sell(update: Update, context: CallbackContext, product_id) -> None:
    user_id = update.callback_query.from_user.id
    quantity = 1  # Can be adjusted if we want to allow selling more than one unit at a time

    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT current_price FROM market WHERE id = ?", (product_id,))
    product = c.fetchone()

    if not product:
        await update.callback_query.message.reply_text('Product does not exist.')
        conn.close()
        return

    c.execute("SELECT balance, portfolio FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()

    if user_data is None:
        await update.callback_query.message.reply_text('User not found.')
        conn.close()
        return

    balance = user_data[0]
    portfolio = json.loads(user_data[1])

    if str(product_id) not in portfolio or portfolio[str(product_id)] < quantity:
        await update.callback_query.message.reply_text('Not enough product in portfolio to sell.')
        conn.close()
        return

    total_revenue = product[0] * quantity

    # Update data
    portfolio[str(product_id)] -= quantity
    if portfolio[str(product_id)] == 0:
        del portfolio[str(product_id)]

    c.execute("UPDATE users SET balance = balance + ?, portfolio = ? WHERE id = ?", (total_revenue, json.dumps(portfolio), user_id))
    c.execute("UPDATE market SET availability = availability + ? WHERE id = ?", (quantity, product_id))
    c.execute("INSERT INTO transactions (user_id, type, product_id, amount, price, date) VALUES (?, 'sell', ?, ?, ?, datetime('now'))", (user_id, product_id, quantity, product[0]))
    conn.commit()
    conn.close()

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(f'You sold {quantity} units of the product for {total_revenue}.', reply_markup=reply_markup)

# Function to display the user's portfolio
async def portfolio(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT portfolio FROM users WHERE id = ?", (user_id,))
    portfolio = c.fetchone()[0]
    portfolio = json.loads(portfolio)
    if not portfolio:
        keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text('Your portfolio is empty.', reply_markup=reply_markup)
    else:
        portfolio_text = 'Your portfolio:\n'
        keyboard = []
        for product_id, quantity in portfolio.items():
            c.execute("SELECT name FROM market WHERE id = ?", (product_id,))
            product_name = c.fetchone()[0]
            portfolio_text += f'{product_name}: {quantity} units\n'
            keyboard.append([InlineKeyboardButton(f'Sell {product_name}', callback_data=f'sell_{product_id}')])
        keyboard.append([InlineKeyboardButton("Back to menu", callback_data='menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(portfolio_text, reply_markup=reply_markup)
    conn.close()

# Function to generate random economic events
async def generate_economic_event(application):
    while True:
        await asyncio.sleep(random.randint(10, 60))  # Random delay between 1 minute and 3 hours
        event_type = random.choice(['boom', 'crash'])
        product_id = random.choice([1, 2, 3, 4, 5, 6])  # Product ID

        conn = sqlite3.connect('game.db')
        c = conn.cursor()
        c.execute("SELECT name, current_price FROM market WHERE id = ?", (product_id,))
        product = c.fetchone()
        if product:
            product_name, current_price = product
            if event_type == 'boom':
                new_price = round(current_price * 1.2, 2)
                message_text = f'Sudden demand increase for {product_name}! Prices are rising.'
            elif event_type == 'crash':
                new_price = round(current_price * 0.8, 2)
                message_text = f'Demand drop for {product_name}! Prices are falling.'

            c.execute("UPDATE market SET current_price = ? WHERE id = ?", (new_price, product_id))
            conn.commit()
            conn.close()

            # Send message to all users
            users = get_all_users()
            keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            for user_id in users:
                try:
                    await application.bot.send_message(chat_id=user_id, text=message_text, reply_markup=reply_markup)
                except telegram.error.Forbidden:
                    # User has blocked the bot
                    continue
                except telegram.error.BadRequest as e:
                    if "Chat not found" in str(e):
                        # Chat not found, possibly the user removed or blocked the bot
                        continue



# async def generate_hossa_bessa_event(application):
#     while True:
#         await asyncio.sleep(random.randint(10, 60))  # Random delay between 1 to 7 days
#         event_type = random.choice(['hossa', 'bessa'])
#         conn = sqlite3.connect('game.db')
#         c = conn.cursor()
#         c.execute("SELECT id, name, current_price FROM market")
#         products = c.fetchall()

#         if event_type == 'hossa':
#             percentage_increase = random.uniform(1.5, 12.0)  # 200% to 1600%
#             for product in products:
#                 product_id, product_name, current_price = product
#                 new_price = round(current_price * percentage_increase, 2)
#                 c.execute("UPDATE market SET current_price = ? WHERE id = ?", (new_price, product_id))
#             message_text = f"Hossa! Prices of all products have increased by {(percentage_increase * 100):.2f}%!"
#             photo_url = 'https://wolfsonton.com/files/hossa.png'  # Replace with your Hossa image URL

#         elif event_type == 'bessa':
#             percentage_decrease = random.uniform(0.5, 0.1)  # 50% to 90%
#             for product in products:
#                 product_id, product_name, current_price = product
#                 new_price = round(current_price * percentage_decrease, 2)
#                 c.execute("UPDATE market SET current_price = ? WHERE id = ?", (new_price, product_id))
#             message_text = f"Bessa! Prices of all products have dropped by {((1 - percentage_decrease) * 100):.2f}%!"
#             photo_url = 'https://wolfsonton.com/files/bessa.png'  # Replace with your Bessa image URL

#         conn.commit()
#         conn.close()

#         # Send message to all users with a photo
#         users = get_all_users()
#         keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
#         reply_markup = InlineKeyboardMarkup(keyboard)
#         for user_id in users:
#             try:
#                 await application.bot.send_photo(chat_id=user_id, photo=photo_url, caption=message_text, reply_markup=reply_markup)
#             except telegram.error.Forbidden:
#                 # User has blocked the bot
#                 continue
#             except telegram.error.BadRequest as e:
#                 if "Chat not found" in str(e):
#                     # Chat not found, possibly the user removed or blocked the bot
#                     continue




def get_all_users():
    conn = sqlite3.connect('game.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users



# # Function to handle the /team command displaying the user's team members
# async def team(update: Update, context: CallbackContext) -> None:
#     user_id = update.effective_user.id

#     conn = sqlite3.connect('game.db')
#     c = conn.cursor()

#     # Get the user's username
#     c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
#     username = c.fetchone()[0]

#     # Get the users who joined using the current user's invite link
#     c.execute("SELECT username FROM users WHERE id IN (SELECT id FROM users WHERE invite_link LIKE ?)", (f"%{user_id}%",))
#     team_members = c.fetchall()

#     team_text = f"Your team (including yourself):\n1. {username}\n"
#     for i, member in enumerate(team_members, start=2):
#         team_text += f"{i}. {member[0]}\n"

#     if not team_members:
#         team_text += "\nNo team members have joined using your invite link yet."

#     conn.close()

#     await update.message.reply_text(team_text)



async def create_company(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Get the company name from the user input
    company_name = ' '.join(context.args)

    if not company_name:
        await update.message.reply_text("Please provide a name for your company using /create_company <CompanyName>.")
        return

    # Check if the user already owns a company
    c.execute("SELECT * FROM companies WHERE owner_id = ?", (user_id,))
    if c.fetchone():
        await update.message.reply_text("You already own a company.")
        return

    # Deduct funds from the user's balance to start the company (e.g., 1000 units)
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    balance = c.fetchone()[0]
    company_cost = 100.0

    if balance < company_cost:
        await update.message.reply_text("You don't have enough funds to create a company.")
        return

    c.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (company_cost, user_id))
    c.execute("INSERT INTO companies (name, owner_id) VALUES (?, ?)", (company_name, user_id))

    conn.commit()
    conn.close()

    await update.message.reply_text(f"Congratulations! You have successfully created the company '{company_name}'.")



async def show_company(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Check if the user owns a company
    c.execute("SELECT * FROM companies WHERE owner_id = ?", (user_id,))
    company = c.fetchone()

    if not company:
        await update.message.reply_text("You do not own a company.")
        return

    company_id, name, owner_id, value, profit_margin, team = company
    company_info = (f"Company Name: {name}\n"
                    f"Value: {value:.2f} units\n"
                    f"Profit Margin: {profit_margin:.2%}\n"
                    f"Team Size: {team}\n\n"
                    "Company Members:\n")

    # Get members of the company
    c.execute("SELECT u.username, m.role, m.status FROM company_members m JOIN users u ON m.user_id = u.id WHERE m.company_id = ?",
              (company_id,))
    members = c.fetchall()

    if members:
        for member in members:
            username, role, status = member
            company_info += f"Username: {username}, Role: {role}, Status: {status}\n"
    else:
        company_info += "No members in the company.\n"

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data='menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(company_info, reply_markup=reply_markup)
    conn.close()




async def invite_to_company(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Check if the user owns a company
    c.execute("SELECT id FROM companies WHERE owner_id = ?", (user_id,))
    company = c.fetchone()

    if not company:
        await update.message.reply_text("You do not own a company.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /invite <username> <role>")
        return

    target_username = context.args[0]
    role = ' '.join(context.args[1:])

    c.execute("SELECT id FROM users WHERE username = ?", (target_username,))
    target_user = c.fetchone()

    if not target_user:
        await update.message.reply_text("The user you are trying to invite does not exist.")
        return

    target_user_id = target_user[0]

    # Add invitation to the database
    c.execute("INSERT OR REPLACE INTO company_members (company_id, user_id, role, status) VALUES (?, ?, ?, ?)",
              (company[0], target_user_id, role, 'pending'))
    conn.commit()
    conn.close()

    # Notify the invited user
    await context.bot.send_message(chat_id=target_user_id,
                                   text=f"You have been invited to join the company by {update.effective_user.username} as {role}. Use /accept to join the company or /decline to reject the invitation.")
    await update.message.reply_text(f"Invitation sent to {target_username}.")



async def accept_invitation(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Check for pending invitations
    c.execute("SELECT company_id, role FROM company_members WHERE user_id = ? AND status = 'pending'", (user_id,))
    invitation = c.fetchone()

    if not invitation:
        await update.message.reply_text("You have no pending invitations.")
        return

    company_id, role = invitation

    # Accept the invitation
    c.execute("UPDATE company_members SET status = 'accepted' WHERE company_id = ? AND user_id = ?",
              (company_id, user_id))
    conn.commit()

    # Get company name
    c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
    company_name = c.fetchone()[0]

    conn.close()

    await update.message.reply_text(f"You have joined the company '{company_name}' as {role}.")

async def decline_invitation(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Check for pending invitations
    c.execute("SELECT company_id FROM company_members WHERE user_id = ? AND status = 'pending'", (user_id,))
    invitation = c.fetchone()

    if not invitation:
        await update.message.reply_text("You have no pending invitations.")
        return

    company_id = invitation[0]

    # Decline the invitation
    c.execute("DELETE FROM company_members WHERE company_id = ? AND user_id = ?", (company_id, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text("You have declined the invitation.")




async def username(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    conn = sqlite3.connect('game.db')
    c = conn.cursor()

    # Sprawdź, czy użytkownik chce zmienić swój username
    if context.args:
        new_username = context.args[0]

        # Sprawdź, czy username jest już używany
        c.execute("SELECT id FROM users WHERE username = ?", (new_username,))
        if c.fetchone():
            await update.message.reply_text(f"The username '{new_username}' is already taken. Please choose a different one.")
        else:
            # Zaktualizuj username w tabeli users
            c.execute("UPDATE users SET username = ? WHERE id = ?", (new_username, user_id))
            conn.commit()
            await update.message.reply_text(f"Your username has been changed to '{new_username}'.")
    else:
        # Wyświetl aktualny username
        c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        username = c.fetchone()[0]
        await update.message.reply_text(f"Your current username is '{username}'.")

    conn.close()



# Main bot function
def main() -> None:
    # Initialize database
    init_db()

    # Bot token
    application = Application.builder().token("7244283258:AAGiCySykhK9alu-YOr8FtdA8K7Q177Atbw").build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("portfolio", portfolio))
    application.add_handler(CommandHandler("how_to_play", how_to_play))
    # application.add_handler(CommandHandler("team", team))
    application.add_handler(CommandHandler("create_company", create_company))
    application.add_handler(CommandHandler("show_company", show_company))
    application.add_handler(CommandHandler("username", username))
    application.add_handler(CommandHandler("invite", invite_to_company))
    application.add_handler(CommandHandler("accept", accept_invitation))
    application.add_handler(CommandHandler("decline", decline_invitation))




    # Start generating random economic events
    loop = asyncio.get_event_loop()
    loop.create_task(generate_economic_event(application))
    # loop.create_task(generate_hossa_bessa_event(application))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
