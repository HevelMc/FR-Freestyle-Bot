import os, asyncio, re, yaml, random
from discord import Permissions, Thread, ApplicationContext, Interaction, \
    Bot, Intents, Embed,  InteractionMessage, Message, ButtonStyle, \
    RawReactionActionEvent, Reaction, User, Member, SelectOption, \
    MessageReference, option
from discord.ui import View, Button, button, select
from discord.ext.commands import has_permissions
from discord.ext import tasks
from dotenv import load_dotenv

with open("local-config.yml") as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

load_dotenv()

intents = Intents.all()
bot = Bot(intents=intents)
modos = bot.create_group("modos", "Commandes réservées aux modérateurs.")

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    update_stats_loop.start()
    bot.add_view(CandidView())

@bot.event
async def on_message(message: Message):
    if message.channel.id != config["candid_channel_id"]: return
    if message.author.id == bot.user.id: return

    await message.delete(reason="Message dans le salon candidature")
    if not message.author.bot:
        await message.channel.send(f"{message.author.mention} Vous ne pouvez pas envoyer de message ici, utilisez la commande **/candidature**.", delete_after=5)


@bot.slash_command(guild_ids=[config["guild_id"]], description="Permet de candidater pour obtenir le rôle Freestyler")
async def candidature(ctx: ApplicationContext):
    
    if config["freestyler_role_id"] in [r.id for r in ctx.author.roles]:
        return await ctx.respond("Vous avez déjà le rôle Freestyler. Vous ne pouvez pas candidater à nouveau.")

    interact: Interaction = await ctx.respond(f"Candidature de <@{ctx.author.id}>")
    original_message: InteractionMessage = await interact.original_message()
    thread: Thread = await original_message.create_thread(name="Candidature de " + ctx.author.name, auto_archive_duration=60)

    def check(msg):
        return msg.author == ctx.author and msg.channel.id == thread.id

    pseudo = None
    await thread.send(content=f"**➡️ {ctx.author.mention} Quel est ton pseudo en jeu ?**")
    try:
        pseudoRspMsg = await bot.wait_for("message", check=check, timeout=60)
        pseudo = pseudoRspMsg.content
    except asyncio.TimeoutError:
        return await print_timeout(thread, original_message)
    
    age = None
    await thread.send(content="**🔢 Quel âge as-tu ?**")
    while True:
        try:
            ageRspMsg = await bot.wait_for("message", check=check, timeout=60)
            age = ageRspMsg.content
            striped_age = ''.join(c for c in age if c in "0123456789")
            if striped_age == '':
                await thread.send("❌ Veuillez indiquer votre âge (en chiffre).")
            else:
                parsed_age = int(striped_age)
                break
        except asyncio.TimeoutError:
            return await print_timeout(thread, original_message)

    url = None
    await thread.send(content="**🔗 Lien de ta vidéo showcase**\n" + "*Seules les vidéos YouTube de type compilation de 1mn30 à 3mn sont acceptées.*")
    while True:
        try:
            urlRspMsg = await bot.wait_for("message", check=check, timeout=120)
            url = urlRspMsg.content
            if re.match("^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube(-nocookie)?\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$", url):
                break
            else:
                await thread.send("❌ Il ne s'agit pas d'une vidéo Youtube, veuillez envoyer un autre lien...")
        except asyncio.TimeoutError:
            return await print_timeout(thread, original_message)
    
    await post_candid(ctx.author, pseudo, parsed_age, url)

    await thread.send("✅ Votre candidature a bien été enregistrée.")
    await thread.archive(True)
    await original_message.delete()
    

async def post_candid(author: User, pseudo: str, age: int, url: str):
    candid_channel = bot.get_channel(config["candid_channel_id"])
    embedMsg = await candid_channel.send(f"Candidature de {author.mention}\n{url}")
    embed=Embed(title="", color=0xff8040)
    embed.add_field(name="Pseudo", value=pseudo, inline=False)
    embed.add_field(name="Âge", value=f"{age} ans", inline=False)
    embed.add_field(name="Statut", value="⏰ En cours de jugement", inline=False)
    embed.add_field(name="Niveau", value="⏰ En cours de jugement", inline=False)
    embed.set_footer(text="FREESTYLE FRANCE")
    
    await embedMsg.edit(embeds=[*embedMsg.embeds, embed], view=CandidView())
    await embedMsg.add_reaction('1️⃣')
    await embedMsg.add_reaction('2️⃣')
    await embedMsg.add_reaction('3️⃣')
    await embedMsg.add_reaction('4️⃣')

    if age < 13:
        asyncio.create_task(wrong_age_callback(candid_channel, embedMsg))

async def wrong_age_callback(candid_channel, embedMsg):
    await asyncio.sleep(random.randrange(20, 60))
    await decline_candid(candid_channel, embedMsg.id)

async def decline_candid(channel, msg_id):
    msg = await channel.fetch_message(msg_id)
    embeds: list(Embed) = msg.embeds
    embed: Embed = embeds[-1]
    embed.color = 0xff8080
    embed.set_field_at(2, name="Statut", value="❌ Déclinée", inline=False)
    embed.remove_field(3)
    embeds[-1] = embed
    view = View.from_message(msg)
    view.clear_items()
    view.stop()
    await msg.edit(embeds=embeds, view=view)

class CandidView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @select(custom_id="level", placeholder = "Niveau",
        options = [
            SelectOption(label="Niveau 1"),
            SelectOption(label="Niveau 2"),
            SelectOption(label="Niveau 3"),
            SelectOption(label="Niveau 4"),
        ])
    async def select_callback(self, select, interaction):
        if interaction.user.guild_permissions.manage_roles:
            msg = interaction.message
            if msg == None: return
            embeds: list(Embed) = msg.embeds
            embed: Embed = embeds[-1]
            embed.set_field_at(3, name="Niveau", value=select.values[0], inline=False)
            embeds[-1] = embed
            await msg.edit(embeds=embeds, view=self)
            return await interaction.response.send_message(f"{select.values[0]} choisi, veuillez approuver pour finaliser l'inscription.", ephemeral=True, delete_after=5)
        else:
            await interaction.response.send_message("Vous n'avez pas la permission", ephemeral=True, delete_after=5)

    @button(label="Approuver", style=ButtonStyle.green, custom_id="validate")
    async def validate_callback(self, button, interaction: Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message(f"Vous n'avez pas la permission de faire ceci", ephemeral=True, delete_after=5)
        msg: Message = interaction.message
        if msg == None: return await interaction.response.send_message(f"error #0 : invalid message", ephemeral=True, delete_after=60)
        embeds: list(Embed) = msg.embeds
        embed: Embed = embeds[-1]
        user_id = int(re.findall("Candidature de <@(.{18})>", msg.content)[0])
        user = interaction.guild.get_member(user_id)
        if user == None: return await interaction.response.send_message(f"error #1 : invalid user", ephemeral=True, delete_after=60)
        if embed._fields[3].value == "⏰ En cours de jugement":
            return await interaction.response.send_message(f"Veuillez d'abord choisir un niveau.", ephemeral=True, delete_after=5)
        roles = bot.get_guild(interaction.guild_id).roles
        role = [r for r in roles if r.name == embed._fields[3].value][0] or None
        if role == None: return await interaction.response.send_message(f"error #2/0 : invalid {embed._fields[3].value} role", ephemeral=True, delete_after=60)
        await user.add_roles(role, reason="Rank up")
        role_fs = [r for r in roles if r.name == "Freestyler"][0] or None
        if role_fs == None: return await interaction.response.send_message(f"error #2/1 : invalid Freestyler role", ephemeral=True, delete_after=60)
        await user.add_roles(role_fs, reason="Rank up")
        role_member = [r for r in roles if r.name == "Membre"][0] or None
        if role_member == None: return await interaction.response.send_message(f"error #2/2 : invalid Membre role", ephemeral=True, delete_after=60)
        await user.remove_roles(role_member, reason="Rank up")
        output = await self.on_click(interaction, "✅ Approuvée", 0x00ff00)
        return await interaction.response.send_message(f"{output}\nLes rôles Freestyler et {role.name} ont été ajoutés à l'utilisateur {user.mention} !", ephemeral=True, delete_after=5)


    @button(label="Décliner", style=ButtonStyle.red, custom_id="decline")
    async def decline_callback(self, button, interaction):
        msg = await self.on_click(interaction, "❌ Déclinée", 0xff8080)
        return await interaction.response.send_message(msg, ephemeral=True, delete_after=5)
    @button(label="Incorrecte", style=ButtonStyle.gray, custom_id="incorrect")
    async def incorrect_callback(self, button, interaction):
        msg = await self.on_click(interaction, "❗ Incorrecte", 0x808080)
        return await interaction.response.send_message(msg, ephemeral=True, delete_after=5)
    
    async def on_click(self, interaction, text: str, color) -> str:
        if interaction.user.guild_permissions.manage_roles:
            msg = interaction.message
            if msg == None: return
            embeds: list(Embed) = msg.embeds
            embed: Embed = embeds[-1]
            embed.color = color
            embed.set_field_at(2, name="Statut", value=text, inline=False)
            if text == "❌ Déclinée" or text == "❗ Incorrecte":
                embed.remove_field(3)
            embeds[-1] = embed
            self.clear_items()
            self.stop()
            await msg.edit(embeds=embeds, view=self)
            return "Candidature marquée comme " + text + " !"
        else:
            return "Vous n'avez pas la permission de faire ceci"

async def print_timeout(thread: Thread, msg: InteractionMessage) -> None:
    await thread.send(content="Vous n'avez pas répondu à temps... Archivage du fil, veuillez recommencer.")
    await thread.archive(True)
    await msg.delete()

@modos.command(guild_ids=[config["guild_id"]])
@has_permissions(manage_messages=True)
@option("message_id", str, required=True)
@option("embed_id", int, required=True)
@option("field_id", int, required=True)
@option("name", str, required=False, default='')
@option("value", str, required=False, default='')
@option("inline", bool, required=False, default=True)
async def edit_field(ctx: ApplicationContext, message_id, embed_id, field_id, name, value, inline):
    if not ctx.author.guild_permissions.manage_messages:
        return await ctx.respond("❌ Vous n'avez pas la permission.", ephemeral=True)
    try:
        msg: Message = await ctx.fetch_message(int(message_id))
    except ValueError:
        return await ctx.respond("An error occured : message id is invalid.", ephemeral=True)
    if msg == None: return await ctx.respond("An error occured : message not found.", ephemeral=True)
    embeds = msg.embeds
    embed: Embed = msg.embeds[embed_id] or None
    if embed == None: return await ctx.respond("An error occured : embed not found.", ephemeral=True)
    if name == '' or value == '':
        if len(embed._fields) <= field_id:
            return await ctx.respond("An error occured : field not found.", ephemeral=True)
        embed.remove_field(field_id)
    elif len(embed._fields) > field_id:
        embed.set_field_at(field_id, name=name, value=value, inline=inline)
    else:
        embed.add_field(name=name, value=value, inline=inline)
    embeds[embed_id] = embed
    await msg.edit(embeds=embeds)
    return await ctx.respond("Message has been successfully edited.", ephemeral=True)

@modos.command(guild_ids=[config["guild_id"]])
@has_permissions(manage_messages=True)
@option("message_id", str, required=True)
@option("embed_id", int, required=True)
@option("color", int, required=True)
async def edit_color(ctx: ApplicationContext, message_id, embed_id, color):
    if not ctx.author.guild_permissions.manage_messages:
        return await ctx.respond("❌ Vous n'avez pas la permission.", ephemeral=True)
    try:
        msg: Message = await ctx.fetch_message(int(message_id))
    except ValueError:
        return await ctx.respond("An error occured : message id is invalid.", ephemeral=True)
    if msg == None: return await ctx.respond("An error occured : message not found.", ephemeral=True)
    embeds = msg.embeds
    embed: Embed = msg.embeds[embed_id] or None
    if embed == None: return await ctx.respond("An error occured : embed not found.", ephemeral=True)
    embed.color = color
    embeds[embed_id] = embed
    await msg.edit(embeds=embeds)
    return await ctx.respond("Message has been successfully edited.", ephemeral=True)

@modos.command(guild_ids=[config["guild_id"]])
@option("author", User, required=True)
@option("pseudo", str, required=True)
@option("age", int, required=True)
@option("url", str, required=True)
async def add_candid(ctx: ApplicationContext, user: User, pseudo: str, age: int, url: str):
    if not ctx.author.guild_permissions.manage_messages:
        return await ctx.respond("❌ Vous n'avez pas la permission.", ephemeral=True)
    await post_candid(user, pseudo, age, url)
    return await ctx.respond("✅ La candidature a bien été enregistrée.", ephemeral=True)

async def update_stats():
    guild: Guild = bot.get_guild(config["guild_id"])
    for role in [["Membre", "total_id", "Total"], ["Niveau 1", "level_1_id", "Niveau 1"], ["Niveau 2", "level_2_id", "Niveau 2"], ["Niveau 3", "level_3_id", "Niveau 3"], ["Niveau 4", "level_4_id", "Niveau 4"]]:
        # Count the number of members with role
        drole = [r for r in guild.roles if r.name == role[0]][0]
        print(f"{role[2]} : {len(drole.members)}")
        # Update the channel name
        channel: TextChannel = bot.get_channel(config[role[1]])
        print(channel.name)
        if channel.name != f"{role[2]} : {len(drole.members)}":
            await channel.edit(name=f"{role[2]} : {len(drole.members)}")

@tasks.loop(minutes=10)
async def update_stats_loop():
    await update_stats()

bot.run(os.environ['DISCORD_TOKEN'])