import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime
import json
import os
from asyncio import create_task, sleep

# ===== CONFIG =====
TOKEN = ''
GUILD_ID =   # server id
ROLURI_ADMIN = [, 222222222222222222]  # id roluri admin
ROLURI_PONTAJ = [, 444444444444444444]  # id roluri care pot sa faca pontaj
ID_CANAL =   #Channel id where you want the EMBED to be posted in.

DATA_FILE = "pontaje.json"

LANG = "EN"

TRANSLATIONS = {
    "NO_PERMISSION": {
        "RO": "❌ **Nu ai permisiunea!**",
        "EN": "❌ **You don't have permission!**"
    },
    "ALREADY_CLOCKED_IN": {
        "RO": "⚠️ **Esti deja pontat.**",
        "EN": "⚠️ **You're already clocked in.**"
    },
    "CLOCK_IN_SUCCESS": {
        "RO": "✅ **Ai pornit pontajul la: {time}**",
        "EN": "✅ **Clock-in started at: {time}**"
    },
    "NOT_CLOCKED_IN": {
        "RO": "⚠️ **Nu esti pontat acum.**",
        "EN": "⚠️ **You're not currently clocked in.**"
    },
    "CLOCK_OUT_SUCCESS": {
        "RO": "⏹️ **Ai oprit pontajul la: {time} (Total : {min})**",
        "EN": "⏹️ **You clocked out at: {time} (Total : {min})**"
    },
    "PAUSE_STARTED": {
        "RO": "⏸️ **Ai pus pontajul pe pauza, dupa 5 minute o sa se ponteze in continuare! Nu vei putea opri pontajul pana nu se va termina pauza!**",
        "EN": "⏸️ **You've paused your clock-in. It will resume automatically after 5 minutes! You won't be able to stop the clock-in until the pause ends!**"
    },
    "PAUSE_ENDED": {
        "RO": "▶️ **Pauza de 5 minute s-a terminat, pontajul a fost reluat automat.**",
        "EN": "▶️ **Your 5 minute pause ended, clock-in has resumed automatically.**"
    },


    "NO_CLOCK_DATA": {
        "RO": "⚠️ Nu exista date de pontaj.",
        "EN": "⚠️ There is no clock-in data."
    },
    "TOTAL_CLOCK_TITLE": {
        "RO": "**Pontaj total:**\n",
        "EN": "**Total Clocked Time:**\n"
    },
    "NO_USER_CLOCKED": {
        "RO": "⚠️ {name} nu are pontaj.",
        "EN": "⚠️ {name} has no clocked time."
    },
    "USER_CLOCKED_TOTAL": {
        "RO": "📊 Pontaj {name}: {min} minute.",
        "EN": "📊 Clocked time for {name}: {min} minutes."
    },
    "USER_RESET": {
        "RO": "✅ Pontajul lui {name} a fost sters.",
        "EN": "✅ {name}'s clock-in data has been reset."
    },
    "ALL_RESET": {
        "RO": "✅ Toate pontajele au fost sterse.",
        "EN": "✅ All clock-in data has been reset."
    },
    "DESCRIPTION": {
        "RO": "Foloseste butoanele de mai jos pentru a incepe/opri sau a pune pauza la pontaj.",
        "EN": "Use the buttons below to start/stop or pause your clock-in."
    }
}

# ===== FUNCTII =====

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def has_any_role(member: discord.Member, roluri):
    return any(role.id in roluri for role in member.roles)

def round_time_5min(dt: datetime):
    minut_rotunjit = (dt.minute // 5) * 5
    return dt.replace(minute=minut_rotunjit, second=0, microsecond=0)

def calculeaza_timp_total(sesiuni):
    total_min = 0
    for sesiune in sesiuni:
        start = datetime.fromisoformat(sesiune["start"])
        end = sesiune["end"]
        if end is None:
            end = datetime.now()
        else:
            end = datetime.fromisoformat(end)
        dur = (end - start).total_seconds() / 60
        total_min += dur
    total_min_5 = 5 * round(total_min / 5)
    return total_min_5

def tr(key, **kwargs):
    text = TRANSLATIONS.get(key, {}).get(LANG, key)
    return text.format(**kwargs)

# ===== BUTOANE =====
class PontajView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start Pontaj", style=discord.ButtonStyle.green)
    async def start_pontaj(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, ROLURI_PONTAJ):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return

        data = load_data()
        uid = str(interaction.user.id)
        acum = round_time_5min(datetime.now())

        user_data = data.get(uid, {})
        if user_data.get("status") == "in_pontaj":
            await interaction.response.send_message(tr("ALREADY_CLOCKED_IN"), ephemeral=True)
            return

        user_data["status"] = "in_pontaj"
        user_data.setdefault("sessions", [])
        user_data["sessions"].append({"start": acum.isoformat(), "end": None})
        data[uid] = user_data
        save_data(data)

        await interaction.response.send_message(tr("CLOCK_IN_SUCCESS", time=acum.strftime('%H:%M')), ephemeral=True)

    @discord.ui.button(label="Stop Pontaj", style=discord.ButtonStyle.red)
    async def stop_pontaj(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, ROLURI_PONTAJ):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return


        data = load_data()
        uid = str(interaction.user.id)
        user_data = data.get(uid)

        if not user_data.get("sessions"):
            await interaction.response.send_message(tr("NO_USER_CLOCKED", name=interaction.user.display_name), ephemeral=True)
            return

        if not user_data or user_data.get("status") != "in_pontaj":
            await interaction.response.send_message(tr("NOT_CLOCKED_IN"), ephemeral=True)
            return

        acum = round_time_5min(datetime.now())

        for sesiune in reversed(user_data["sessions"]):
            if sesiune["end"] is None:
                sesiune["end"] = acum.isoformat()
                break

        user_data["status"] = "not_pontat"
        data[uid] = user_data
        save_data(data)

        total_min = calculeaza_timp_total(user_data["sessions"])

        await interaction.response.send_message(
            tr("CLOCK_OUT_SUCCESS", time=acum.strftime('%H:%M'), min=int(total_min)), ephemeral=True
        )

    @discord.ui.button(label="Pauza Pontaj", style=discord.ButtonStyle.grey)
    async def pauza_pontaj(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, ROLURI_PONTAJ):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return

        data = load_data()
        uid = str(interaction.user.id)
        user_data = data.get(uid)

        if not user_data or user_data.get("status") != "in_pontaj":
            await interaction.response.send_message(tr("NOT_CLOCKED_IN"), ephemeral=True)
            return

        
        user_data["status"] = "in_pauza"
        data[uid] = user_data
        save_data(data)

        await interaction.response.send_message(
            tr("PAUSE_STARTED"), ephemeral=True
        )

        
        async def resume_after_pauza():
            await sleep(300)  
            data = load_data()
            user_data = data.get(uid)
            if user_data and user_data.get("status") == "in_pauza":
                user_data["status"] = "in_pontaj"
                data[uid] = user_data
                save_data(data)
                
                try:
                    user = await interaction.client.fetch_user(int(uid))
                    await user.send(tr("PAUSE_ENDED"))
                except:
                    pass

        create_task(resume_after_pauza())

#########################
intents = discord.Intents.default()
intents.members = True 

def este_admin(member: discord.Member):
    return has_any_role(member, ROLURI_ADMIN)
bot = commands.Bot(command_prefix="!", intents=intents)

#########################

class PontajAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def check_admin(self, interaction: discord.Interaction):
        return has_any_role(interaction.user, ROLURI_ADMIN)

    @app_commands.command(name="showclockin", description="Show a member's clock-in data")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(membru="Membrul pentru care vrei pontajul")
    async def pontaj(self, interaction: discord.Interaction, membru: discord.Member):
        if not self.check_admin(interaction):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return

        data = load_data()
        uid = str(membru.id)
        user_data = data.get(uid)

        if not user_data or not user_data.get("sessions"):
            await interaction.response.send_message(tr("NO_USER_CLOCKED", name = membru.display_name), ephemeral=True)
            return

        total_min = calculeaza_timp_total(user_data["sessions"])
        await interaction.response.send_message(tr("USER_CLOCKED_TOTAL", name = membru.display_name, min= int(total_min)), ephemeral=True)

    @app_commands.command(name="showtotal", description="Show the clock-in data for all members")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def pontajtotal(self, interaction: discord.Interaction):
        if not self.check_admin(interaction):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return

        data = load_data()
        if not data:
            await interaction.response.send_message(tr("NO_CLOCK_DATA"), ephemeral=True)
            return

        msg = tr("TOTAL_CLOCK_TITLE")
        for uid, info in data.items():
            member = interaction.guild.get_member(int(uid))
            if not member:
                continue
            total_min = calculeaza_timp_total(info.get("sessions", []))
            msg += f"- {member.display_name}: {int(total_min)} min\n"

        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="resetclockin", description="Delete a member's clock-in data")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.describe(membru="Membrul caruia ii stergi pontajul")
    async def pontajreset(self, interaction: discord.Interaction, membru: discord.Member):
        if not self.check_admin(interaction):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return

        data = load_data()
        uid = str(membru.id)
        if uid in data:
            del data[uid]
            save_data(data)
            await interaction.response.send_message(tr("USER_RESET", name=membru.display_name), ephemeral=True)
        else:
            await interaction.response.send_message(tr("NO_USER_CLOCKED", name=membru.display_name), ephemeral=True)

    @app_commands.command(name="totalclockinreset", description="Delete all clock-in data")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def pontajtotal_reset(self, interaction: discord.Interaction):
        if not self.check_admin(interaction):
            await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
            return

        save_data({})
        await interaction.response.send_message(tr("ALL_RESET"), ephemeral=True)

#########################


#########################


@bot.event
async def on_ready():
    await bot.add_cog(PontajAdmin(bot))
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print("Error syncing slash commands:", e)

    print(f"Botul este online ca {bot.user}")
    canal = bot.get_channel(ID_CANAL)
    if canal is None:
        print("No channel found with the ID")
        return

    
    async for mesaj in canal.history(limit=20):
        if mesaj.author == bot.user and mesaj.embeds:
            print("Embed-ul cu pontaj exista deja in canal.")
            return

    embed = discord.Embed(
        title="TITLE",
        description=tr("DESCRIPTION"),
        color=0x442e1b
    )
    embed.set_thumbnail(url="")
    embed.set_author(name="Author Name", icon_url="")
    view = PontajView()
    await canal.send(embed=embed, view=view)
    #bot.add_view(PontajView())
    print("Embed sent to channel.")


@bot.tree.command(name="sendembed", description="Send the embed", guild=discord.Object(id=GUILD_ID))
async def afiseaza_pontaj(interaction: discord.Interaction):
    if not has_any_role(interaction.user, ROLURI_ADMIN):
        await interaction.response.send_message(tr("NO_PERMISSION"), ephemeral=True)
        return
    
    embed = discord.Embed(
        title="TITLE",
        description=tr("DESCRIPTION"),
        color=0x442e1b
    )
    embed.set_thumbnail(url="")
    embed.set_author(name="Author Name", icon_url="")

    view = PontajView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)




bot.run(TOKEN)


