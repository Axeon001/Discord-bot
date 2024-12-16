import discord
import os
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# Инициализация Flask-сервера
app = Flask(__name__)


@app.route("/")
def home():
    return "Бот работает!"


def run_flask():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    server_thread = Thread(target=run_flask)
    server_thread.start()


# Инициализация Discord бота
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Подключение к MongoDB
MONGO_URL = "mongodb+srv://Axeon:erkosh2008kaldybek@limitlessrising.gtbj5.mongodb.net/?retryWrites=true&w=majority"
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["discord_bot"]
collection = db["players"]


# Формулы
def calculate_exp_for_level(level):
    if level <= 10:
        return level * 100
    elif level <= 20:
        return level * 200
    elif level <= 50:
        return level * 300
    return level * 500


def calculate_os(stats):
    return int((stats['strength'] * 2) + (stats['agility'] * 1.5) +
               (stats['durability'] * 1.5) + (stats['endurance'] * 1.2) +
               (stats['intellect'] * 1.8))


def determine_rank(total_stats):
    if total_stats >= 1001:
        return "S"
    elif total_stats >= 701:
        return "A"
    elif total_stats >= 501:
        return "B"
    elif total_stats >= 301:
        return "C"
    elif total_stats >= 151:
        return "D"
    elif total_stats >= 51:
        return "E"
    return "F"


# Событие запуска
@bot.event
async def on_ready():
    print(f"Бот {bot.user} запущен!")


# Команда регистрации
@bot.command()
async def register(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    user_id = str(target.id)
    player = await collection.find_one({"_id": user_id})
    
    if player:
        await ctx.send(f"{target.mention}, уже зарегистрирован!")
        return

    # Если регистрируем другого пользователя, проверяем права
    if member and not ctx.author.guild_permissions.administrator:
        await ctx.send("Вы не можете регистрировать других пользователей!")
        return

    # Запрос имени персонажа
    await ctx.send(f"{target.mention}, введите имя вашего персонажа:")
    try:
        name_msg = await bot.wait_for(
            'message', 
            timeout=30.0, 
            check=lambda m: m.author == ctx.author
        )
        name = name_msg.content.strip()
    except:
        await ctx.send(
            f"{ctx.author.mention}, вы не ответили вовремя. Регистрация отменена."
        )
        return

    # Запрос характеристик
    stats = {}
    for stat in ["strength", "agility", "durability", "endurance", "intellect"]:
        await ctx.send(f"Введите {stat} (1-100):")
        try:
            msg = await bot.wait_for(
                'message',
                timeout=30.0,
                check=lambda m: m.author == ctx.author and m.content.isdigit()
            )
            stats[stat] = min(100, max(1, int(msg.content)))  # Ограничиваем значения
        except:
            await ctx.send(
                f"{ctx.author.mention}, вы не ответили вовремя. Регистрация отменена."
            )
            return

    # Расчёт OS, ранга и сохранение данных
    total_stats = sum(stats.values())
    rank = determine_rank(total_stats)
    os = calculate_os(stats)

    player = {
        "_id": user_id,
        "name": name,
        "strength": stats["strength"],
        "agility": stats["agility"],
        "durability": stats["durability"],
        "endurance": stats["endurance"],
        "intellect": stats["intellect"],
        "level": 1,
        "exp": 0,
        "rank": rank,
        "os": os
    }

    await collection.insert_one(player)
    await ctx.send(embed=discord.Embed(
        title="Регистрация завершена!",
        description=f"Добро пожаловать, **{name}**!\nВаш ранг: {rank}",
        color=discord.Color.green()))


# Команда лидеров
@bot.command()
async def leaderboard(ctx):
    players = await collection.find().sort("os", -1).to_list(10)
    if not players:
        await ctx.send("Лидерборд пока пуст.")
        return

    embed = discord.Embed(title="🏆 Лидерборд", color=discord.Color.gold())
    for index, player in enumerate(players):
        embed.add_field(name=f"{index + 1}. {player['name']}",
                        value=f"OS: {player['os']} | Ранг: {player['rank']}",
                        inline=False)
    await ctx.send(embed=embed)


# Команда обновления OS
@bot.command()
async def update_os(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    user_id = str(target.id)
    player = await collection.find_one({"_id": user_id})
    
    if not player:
        await ctx.send(f"{target.mention} не зарегистрирован!")
        return

    # Расчёт OS и ранга
    os = calculate_os(player)
    rank = determine_rank(
        sum(player[key] for key in ["strength", "agility", "durability", "endurance", "intellect"])
    )
    await collection.update_one({"_id": user_id}, {"$set": {"os": os, "rank": rank}})
    await ctx.send(
        embed=discord.Embed(
            title="OS обновлено!",
            description=f"Новый OS: {os}\nВаш ранг: {rank}",
            color=discord.Color.purple()
        )
    )


# Команда сброса персонажа
@bot.command()
@commands.has_permissions(administrator=True)  # Требуем права администратора
async def reset(ctx, member: discord.Member = None):
    # Если пинг не был указан, сбрасываем данные для вызывающего пользователя
    target = member if member else ctx.author
    user_id = str(target.id)

    player = await collection.find_one({"_id": user_id})
    if not player:
        await ctx.send(f"{target.mention} не зарегистрирован!")
        return

    # Удаляем персонажа из базы данных
    await collection.delete_one({"_id": user_id})
    await ctx.send(embed=discord.Embed(
        title="Персонаж сброшен!",
        description=(
            f"{target.mention}, ваш персонаж полностью удалён из базы данных.\n"
            "Теперь вы можете зарегистрировать нового персонажа с помощью команды `!register`."
        ),
        color=discord.Color.red()))


@bot.command()
async def edit(ctx, stat: str, value: int, member: discord.Member = None):
    if stat not in ["strength", "agility", "durability", "endurance", "intellect"]:
        await ctx.send(
            "Неверная характеристика. Используйте одну из: strength, agility, durability, endurance, intellect."
        )
        return

    if not (1 <= value <= 100):
        await ctx.send("Значение должно быть в пределах от 1 до 100.")
        return

    target = member if member else ctx.author
    user_id = str(target.id)
    player = await collection.find_one({"_id": user_id})
    if not player:
        await ctx.send(f"{target.mention} не зарегистрирован!")
        return

    await collection.update_one({"_id": user_id}, {"$set": {stat: value}})
    await ctx.send(embed=discord.Embed(
        title="Характеристика изменена!",
        description=f"{stat.capitalize()} теперь равно {value} у {target.mention}.",
        color=discord.Color.green()))


@bot.command()
async def interface(ctx, member: discord.Member = None):
    # Если указан пинг, получаем данные для указанного пользователя, иначе — для отправителя
    target = member if member else ctx.author
    user_id = str(target.id)

    try:
        player = await collection.find_one({"_id": user_id})
        if not player:
            await ctx.send(f"{target.mention} ещё не зарегистрирован.")
            return

        # Создаём embed с данными игрока
        embed = discord.Embed(title=f"Интерфейс персонажа: {player['name']}",
                              color=discord.Color.blue())
        embed.add_field(name="Физическая сила", value=player['strength'])
        embed.add_field(name="Ловкость", value=player['agility'])
        embed.add_field(name="Прочность", value=player['durability'])
        embed.add_field(name="Выносливость", value=player['endurance'])
        embed.add_field(name="Интеллект", value=player['intellect'])
        embed.add_field(name="Уровень", value=player['level'])
        embed.add_field(
            name="Опыт",
            value=f"{player['exp']} (Доступно очков: {player.get('points', 0)})"
        )
        embed.add_field(name="Ранг", value=player['rank'])
        embed.add_field(name="Общая сила (OS)", value=player['os'])
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Ошибка при выполнении команды interface: {e}")
        await ctx.send("Произошла ошибка при попытке получить данные.")


@bot.command()
async def add_exp(ctx, exp: int, member: discord.Member = None):
    if exp <= 0:
        await ctx.send("Количество опыта должно быть положительным.")
        return

    target = member if member else ctx.author
    user_id = str(target.id)
    player = await collection.find_one({"_id": user_id})
    if not player:
        await ctx.send(f"{target.mention} не зарегистрирован!")
        return

    new_exp = player["exp"] + exp
    level = player["level"]
    points = player.get("points", 0)
    required_exp = calculate_exp_for_level(level)

    while new_exp >= required_exp:
        new_exp -= required_exp
        level += 1
        points += 5
        required_exp = calculate_exp_for_level(level)

    await collection.update_one({"_id": user_id},
                                {"$set": {
                                    "exp": new_exp,
                                    "level": level,
                                    "points": points
                                }})

    await ctx.send(embed=discord.Embed(
        title="Опыт добавлен!",
        description=f"{target.mention} получил {exp} опыта!\nТеперь его уровень: {level}\nДоступные очки: {points}\nТекущий опыт: {new_exp}",
        color=discord.Color.orange()))


@bot.command()
async def add_points(ctx, stat: str, points: int, member: discord.Member = None):
    if stat not in ["strength", "agility", "durability", "endurance", "intellect"]:
        await ctx.send(
            "Неверная характеристика. Используйте одну из: strength, agility, durability, endurance, intellect."
        )
        return

    if points <= 0:
        await ctx.send("Количество очков должно быть положительным.")
        return

    target = member if member else ctx.author
    user_id = str(target.id)
    player = await collection.find_one({"_id": user_id})
    if not player:
        await ctx.send(f"{target.mention} не зарегистрирован!")
        return

    available_points = player.get("points", 0)
    if points > available_points:
        await ctx.send(
            f"Недостаточно очков! У вас доступно всего {available_points} очков.")
        return

    new_value = player[stat] + points
    await collection.update_one(
        {"_id": user_id},
        {"$set": {stat: new_value}, "$inc": {"points": -points}})

    await ctx.send(embed=discord.Embed(
        title="Очки распределены!",
        description=f"{points} очков добавлено в {stat.capitalize()} {target.mention}.\nТекущая характеристика: {new_value}",
        color=discord.Color.green()))

@bot.command()
async def help_commands(ctx):
    embed = discord.Embed(
        title="Список доступных команд",
        description="Ниже представлен список всех доступных команд:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="!register [@пользователь]",
        value="Регистрирует персонажа. Если указан пинг, регистрирует другого пользователя (требуются права администратора). Если пинг не указан, регистрирует персонажа для отправителя.",
        inline=False
    )
    embed.add_field(
        name="!reset [@пользователь]",
        value="Сброс персонажа. Полностью удаляет персонажа из базы данных. (администратор)",
        inline=False
    )
    embed.add_field(
        name="!interface [@пользователь]",
        value="Показывает интерфейс текущего персонажа или персонажа другого пользователя, если указан пинг.",
        inline=False
    )
    embed.add_field(
        name="!leaderboard",
        value="Показывает топ-10 игроков по OS (общей силе).",
        inline=False
    )
    embed.add_field(
        name="!add_exp [число] [@пользователь]",
        value="Добавляет указанное количество опыта вашему персонажу или указанному пользователю (администратор).",
        inline=False
    )
    embed.add_field(
        name="!edit [характеристика] [значение] [@пользователь]",
        value="Редактирует одну из характеристик (strength, agility и т.д.) текущего или указанного пользователя (администратор).",
        inline=False
    )
    embed.add_field(
        name="!add_points [характеристика] [число] [@пользователь]",
        value="Добавляет очки в указанную характеристику текущего или другого пользователя. Очки берутся из доступных очков.",
        inline=False
    )
    embed.add_field(
        name="!update_os [@пользователь]",
        value="Обновляет OS и ранг персонажа. Если указан пинг, обновляет данные другого пользователя, иначе — обновляет данные отправителя.",
        inline=False
    )
    embed.add_field(
        name="!help_commands",
        value="Выводит список всех доступных команд с их описанием.",
        inline=False
    )
    await ctx.send(embed=embed)


# Запускаем Flask-сервер
keep_alive()

# Запуск бота
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("BOT_TOKEN")
bot.run(token)  # Исправлено