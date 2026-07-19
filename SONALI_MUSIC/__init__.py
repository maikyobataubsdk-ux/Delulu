from SONALI_MUSIC.core.ffmpeg import ensure_ffmpeg
ensure_ffmpeg()

from SONALI_MUSIC.core.bot import Sona
from SONALI_MUSIC.core.dir import dirr
from SONALI_MUSIC.core.git import git
from SONALI_MUSIC.core.userbot import Userbot
from SONALI_MUSIC.misc import dbb, heroku

from SafoneAPI import SafoneAPI
from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = Sona()
api = SafoneAPI()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
