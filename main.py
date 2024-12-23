import discord
from discord.ext import commands, tasks
import aiohttp
import json
from datetime import datetime

with open('config.json', encoding='utf-8') as config_file:
    config = json.load(config_file)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

standing_message_id = None
standing_channel_id = None
sent_news_ids = set()
news_channel_id = None

async def fetch_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            return data

async def send_standings_to_channel():
    global standing_message_id, standing_channel_id

    url = "https://webws.365scores.com/web/standings/?appTypeId=5&langId=1&timezoneName=Europe/Paris&userCountryId=76&competitions=5930&live=false&withSeasonsFilter=true"
    standings_data = await fetch_data(url)

    groups = standings_data['standings'][0]['groups']
    rows = standings_data['standings'][0]['rows']

    group_standings = {f"Group {group['num']}": [] for group in groups}

    for row in rows:
        group_num = row['groupNum']
        competitor_name = row['competitor']['name']
        points = row['points']
        games_played = row['gamePlayed']
        games_won = row['gamesWon']
        games_drawn = row['gamesEven']
        games_lost = row['gamesLost']
        goals_for = row['for']
        goals_against = row['against']

        group_standings[f"Group {group_num}"].append(
            f"{competitor_name}: {points} pts, {games_played} GP, {games_won} W, {games_drawn} D, {games_lost} L, {goals_for}:{goals_against}"
        )

    if standing_channel_id is None:
        for category in config['categories']:
            if category['name'] == "🏆 FIFA World Cup":
                for channel in category['channels']:
                    if channel['name'] == "📊-standing":
                        standing_channel_id = channel['id']
                        break

    if standing_channel_id:
        channel = bot.get_channel(standing_channel_id)
        if channel:
            embed = discord.Embed(title="FIFA World Cup 2022 Standings", color=discord.Color.blue())
            for group, teams in group_standings.items():
                embed.add_field(name=group, value="\n".join(teams), inline=False)

            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")

            if standing_message_id is None:
                message = await channel.send(embed=embed)
                standing_message_id = message.id
            else:
                message = await channel.fetch_message(standing_message_id)
                await message.edit(embed=embed)
        else:
            print("Standing channel not found.")
    else:
        print("Standing channel not found in the configuration.")

async def send_news_to_channel():
    global news_channel_id

    url = "https://webws.365scores.com/web/news/?appTypeId=5&langId=1&timezoneName=Europe/Paris&userCountryId=76&competitions=5930&isPreview=false"
    news_data = await fetch_data(url)

    if news_channel_id is None:
        for category in config['categories']:
            if category['name'] == "🏆 FIFA World Cup":
                for channel in category['channels']:
                    if channel['name'] == "📢-news":
                        news_channel_id = channel['id']
                        break

    if news_channel_id:
        channel = bot.get_channel(news_channel_id)
        if channel:
            for news in news_data['news']:
                if news['id'] not in sent_news_ids:
                    embed = discord.Embed(title=news['title'], url=news['url'], color=discord.Color.blue())
                    embed.set_image(url=news['image'])
                    
                    try:
                        publish_date = news['publishDate']
                        if len(publish_date) == 25:
                            publish_date = publish_date[:-2] + ':00'
                        embed.set_footer(text=f"Published on: {datetime.fromisoformat(publish_date).strftime('%Y-%m-%d %H:%M:%S')} UTC")
                    except ValueError as e:
                        print(f"Error parsing publish date: {e}")

                    await channel.send(embed=embed)
                    sent_news_ids.add(news['id'])
        else:
            print("News channel not found.")
    else:
        print("News channel not found in the configuration.")

@tasks.loop(minutes=1)
async def update_standings():
    await send_standings_to_channel()

@tasks.loop(minutes=5)
async def check_for_news():
    await send_news_to_channel()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    update_standings.start()
    check_for_news.start()

bot.run(config['bot_token'])
