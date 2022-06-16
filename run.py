import os, asyncio, re, yaml, random
from discord import Permissions, Thread, ApplicationContext, Interaction, \
    Bot, Intents, Embed,  InteractionMessage, Message, ButtonStyle, \
    RawReactionActionEvent, Reaction, User, Member, SelectOption, MessageReference
from discord.ui import View, Button, button, select
from dotenv import load_dotenv

with open("local-config.yml") as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

load_dotenv()

intents = Intents.all()
bot = Bot(intents=intents)

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    bot.add_view(CandidView())

@bot.event
async def on_message(message: Message):
    if message.channel.id != config["candid_channel_id"]: return
    if message.author.id == bot.user.id: return

    await message.delete(reason="Message dans le salon candidature")
    await message.channel.send(f"{message.author.mention} Vous ne pouvez pas envoyer de message ici, utilisez la commande **/candidature**.", delete_after=5)


@bot.slash_command(guild_ids=[config["guild_id"]], description="Permet de candidater pour obtenir le rôle Freestyler")
async def candidature(ctx: ApplicationContext):
    
    if config["freestyler_role_id"] in [r.id for r in ctx.author.roles]:
        return await ctx.respond("Vous avez déjà le rôle Freestyler. Vous ne pouvez pas candidater à nouveau.")

    interact: Interaction = await ctx.respond(f"Candidature de <@{ctx.author.id}>")
    original_message: InteractionMessage = await interact.original_message()
    thread: Thread = await original_message.create_thread(name="Candidature de " + ctx.author.name, auto_archive_duration=60)

    candid_channel = bot.get_channel(config["candid_channel_id"])

    def check(msg):
        return msg.author == ctx.author and msg.channel.id == thread.id

    pseudo = None
    await thread.send(content=f"**➡️ {ctx.author.mention} Quel est ton pseudo en jeu ?**")
    try:
        pseudoRspMsg = await bot.wait_for("message", check=check, timeout=60)
        pseudo = pseudoRspMsg.content
    except asyncio.TimeoutError:
        return await print_timeout(thread)
    
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
            return await print_timeout(thread)

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
            return await print_timeout(thread)
    
    embedMsg = await candid_channel.send(f"Candidature de {ctx.author.mention}\n{url}")
    embed=Embed(title="", color=0x00ff40)
    embed.add_field(name="Pseudo", value=pseudo, inline=False)
    embed.add_field(name="Âge", value=f"{parsed_age} ans", inline=False)
    embed.add_field(name="Statut", value="⏰ En cours de jugement", inline=False)
    embed.add_field(name="Niveau", value="⏰ En cours de jugement", inline=False)
    embed.set_footer(text="FREESTYLE FRANCE")
    await embedMsg.edit(embeds=[*embedMsg.embeds, embed], view=CandidView())
    await embedMsg.add_reaction('1️⃣')
    await embedMsg.add_reaction('2️⃣')
    await embedMsg.add_reaction('3️⃣')

    await thread.send("✅ Votre candidature a bien été enregistrée.")
    await thread.archive(True)
    await original_message.delete()
    if parsed_age < 13:
        await asyncio.sleep(random.randrange(20, 60))
        await decline_candid(candid_channel, embedMsg.id)

async def decline_candid(channel, msg_id):
    msg = await channel.fetch_message(msg_id)
    embeds: list(Embed) = msg.embeds
    embed: Embed = embeds[-1]
    embed.set_field_at(2, name="Statut", value="❌ Déclinée", inline=False)
    embed.remove_field(3)
    embeds[-1] = embed
    await msg.edit(embeds=embeds)

class CandidView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @select(custom_id="level", placeholder = "Niveau",
        options = [
            SelectOption(label="Niveau 1"),
            SelectOption(label="Niveau 2"),
            SelectOption(label="Niveau 3"),
        ])
    async def select_callback(self, select, interaction):
        if interaction.user.guild_permissions.administrator:
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
        if not interaction.user.guild_permissions.administrator:
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
        if role == None: return await interaction.response.send_message(f"error #2 : invalid {embed._fields[3].value} role", ephemeral=True, delete_after=60)
        await user.add_roles(role)
        role_fs = [r for r in roles if r.name == "Freestyler"][0] or None
        if role_fs == None: return await interaction.response.send_message(f"error #3 : invalid Freestyler role", ephemeral=True, delete_after=60)
        await user.add_roles(role_fs)
        output = await self.on_click(interaction, "✅ Approuvée")
        return await interaction.response.send_message(f"{output}\nLes rôles Freestyler et {role.name} ont été ajoutés à l'utilisateur {user.mention} !", ephemeral=True, delete_after=5)


    @button(label="Décliner", style=ButtonStyle.red, custom_id="decline")
    async def decline_callback(self, button, interaction):
        msg = await self.on_click(interaction, "❌ Déclinée")
        return await interaction.response.send_message(msg, ephemeral=True, delete_after=5)
    @button(label="Incorrecte", style=ButtonStyle.gray, custom_id="incorrect")
    async def incorrect_callback(self, button, interaction):
        msg = await self.on_click(interaction, "❗ Incorrecte")
        return await interaction.response.send_message(msg, ephemeral=True, delete_after=5)
    
    async def on_click(self, interaction, text: str) -> str:
        if interaction.user.guild_permissions.administrator:
            msg = interaction.message
            if msg == None: return
            embeds: list(Embed) = msg.embeds
            embed: Embed = embeds[-1]
            embed.set_field_at(2, name="Statut", value=text, inline=False)
            embeds[-1] = embed
            self.clear_items()
            self.stop()
            await msg.edit(embeds=embeds, view=self)
            return "Candidature marquée comme " + text + " !"
        else:
            return "Vous n'avez pas la permission de faire ceci"
        

@bot.event
async def on_raw_reaction_add(payload: RawReactionActionEvent):    
    if payload.channel_id != config["candid_channel_id"]: return
    user: User = await bot.fetch_user(payload.user_id)
    if user is None: return
    if type(user) != Member: return
    member: Member = user
    if member.guild_permissions.manage_roles: return
    message: Message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
    await message.remove_reaction(payload.emoji, user)

async def print_timeout(thread: Thread, msg: InteractionMessage) -> None:
    await thread.send(content="Vous n'avez pas répondu à temps... Archivage du fil, veuillez recommencer.")
    await thread.archive(True)
    await msg.delete()

bot.run(os.environ['DISCORD_TOKEN'])