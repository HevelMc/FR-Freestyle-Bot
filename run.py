import os, asyncio, re, yaml
from discord import Permissions, Thread, ApplicationContext, Interaction, Bot, Intents, Embed, InteractionMessage
from dotenv import load_dotenv

with open("config.yml") as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

load_dotenv()

intents = Intents.all()
bot = Bot(intents=intents)

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")

@bot.slash_command(guild_ids=[config["guild_id"]])
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
    await thread.send(content="**➡️ Quel est ton pseudo en jeu ?**")
    try:
        pseudoRspMsg = await bot.wait_for("message", check=check, timeout=60)
        pseudo = pseudoRspMsg.content
    except asyncio.TimeoutError:
        return await print_timeout(thread)
    
    age = None
    await thread.send(content="**🔢 Quel âge as-tu ?**")
    try:
        ageRspMsg = await bot.wait_for("message", check=check, timeout=60)
        age = ageRspMsg.content
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
    
    embed=Embed(title=f"Candidature de {ctx.author.name}\n", color=0x00ff40)
    embed.add_field(name="Pseudo", value=pseudo, inline=False)
    embed.add_field(name="Âge", value=age, inline=False)
    embed.set_footer(text="FREESTYLE FRANCE")
    embedMsg = await candid_channel.send(embed=embed)
    await embedMsg.add_reaction('1️⃣')
    await embedMsg.add_reaction('2️⃣')
    await embedMsg.add_reaction('3️⃣')
    await embedMsg.add_reaction('✅')
    await embedMsg.add_reaction('🗑️')
    await embedMsg.reply(url)

    await thread.send("✅ Votre candidature a bien été enregistrée.")
    await thread.archive(True)
    await original_message.delete()

async def print_timeout(thread: Thread, msg: InteractionMessage) -> None:
    await thread.send(content="Vous n'avez pas répondu à temps... Archivage du fil, veuillez recommencer.")
    await thread.archive(True)
    await msg.delete()

bot.run(os.environ['DISCORD_TOKEN'])