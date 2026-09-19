# 🎵 Telegram Music Bot (Fully Dynamic Config & ENV Setup)

Is project me Telegram Music Bot me sabhi links, usernames, support channels, repos, aur images/assets ko **Environment Variables (ENV)** ke zariye configurable bana diya gaya hai. Iska faida ye hai ki agar aap is bot ka code kisi Web Portal / Hosting Platform / Deployer website me lagate hain, toh har user apni website se apna links aur details ENV me dal kar bina code touch kiye **apna khud ka customized music bot** bana sakta hai!

---

## 🌟 Key Features (Khas Baatein)

- **100% Dynamic Links & Usernames**: Code me kahin bhi hardcoded links (Support Chat, Channel, Owner, Repo, etc.) nahi hain. Ye sab ENV variables se load hote hain.
- **Custom Images & Media**: Start image, Ping animation/video, status images, sab ENV se control hote hain.
- **Easy Web Website Integration**: Website users bas apne ENV values fill karke bot setup kar sakte hain.
- **Multi-Platform Audio Streaming**: JioSaavn, YouTube, Spotify, Apple Music, Soundcloud support.

---

## 📋 Environment Variables Guide (ENV Details)

Aap in sabhi Variables ko `.env` file me, Heroku Settings me, ya apni Website Hosting panel me set kar sakte hain:

### 1. Mandatory Variables (Zaroori Details)

| Variable Name | Description | Example / Format |
|---|---|---|
| `API_ID` | Telegram API ID ([my.telegram.org](https://my.telegram.org)) | `12345678` |
| `API_HASH` | Telegram API Hash ([my.telegram.org](https://my.telegram.org)) | `abcdef1234567890abcdef1234567890` |
| `BOT_TOKEN` | Bot Token from BotFather ([@BotFather](https://t.me/BotFather)) | `1234567890:ABCdef...` |
| `LOGGER_ID` | Logger Group ID (where logs are sent) | `-1001234567890` |
| `MONGO_DB_URI` | MongoDB Connection URL ([cloud.mongodb.com](https://cloud.mongodb.com)) | `mongodb+srv://user:pass@cluster.mongodb.net/...` |
| `OWNER_ID` | Bot Owner Telegram User ID | `7915069238` |
| `STRING_SESSION` | Pyrogram String Session for Assistant Account | `12345...` |

---

### 2. Dynamic Links & Usernames (Links & Handles Customization)

Is section ki vajah se users website se bina code edit kiye apna khud ka branding kar sakte hain:

| Variable Name | Description | Default Value |
|---|---|---|
| `BOT_NAME` | Aapke Bot ka Name | `sejal 𝑴𝒖𝒔𝒊𝒄 𝑩𝒐𝒕` |
| `BOT_USERNAME` | Aapke Bot ka Username (without `@`) | `MAHI_MUSICSBOT` |
| `OWNER_USERNAME` | Owner ka Telegram Username (without `@`) | `II_ALONE_BOY_Il` |
| `ASSUSERNAME` | Assistant Account ka Username (without `@`) | `II_ALONE_BOY_Il` |
| `SUPPORT_CHAT` | Aapka Support Group Link | `https://t.me/Il_ALONE_BOY_II` |
| `SUPPORT_CHANNEL` | Aapka Updates / News Channel Link | `https://t.me/II_MUSIC_BOT_UPDATE_II` |
| `UPDATES_CHANNEL` | Updates Channel Link | `https://t.me/II_MUSIC_BOT_UPDATE_II` |
| `REPO_URL` | Code Repository / Bot Repo Link | `https://t.me/+tkKtEN7dPFpmMjU1` |
| `UPSTREAM_REPO` | Upstream GitHub Repository | `https://github.com/spicycodez/DeluluMusic` |
| `UPSTREAM_BRANCH` | Git Branch Name | `main` |

---

### 3. Custom Media & Asset URLs (Photo/Video Links)

Aap bot ke start banner, ping video, aur background images ko bhi ENV se change kar sakte hain:

| Variable Name | Description | Default Value |
|---|---|---|
| `START_IMG_URL` | Bot Start Banner Image URL | `https://litter.catbox.moe/xr9jf82b2umeke7j.jpg` |
| `PING_IMG_URL` | Ping Command Video/Gif URL | `https://litter.catbox.moe/xyedznhk80hmial2.mp4` |
| `PLAYLIST_IMG_URL` | Playlist Command Image URL | `https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg` |
| `STATS_IMG_URL` | Stats Command Image URL | `https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg` |
| `STREAM_IMG_URL` | Stream Status Image URL | `https://graph.org/file/4fb9a698630aa5b47be05-060979d72b7752fc8f.jpg` |

---

## 🚀 Website Panel / Web Deployment Setup Guide

Agar aap is repo ko kisi web platform (jaise ki Bot Hosting Website, Panel, ya Heroku/VPS) me add kar rahe hain jahan se users 1-Click me apna bot create kar sakein:

1. **Website Form Fields**: Apni website ke deployment form me uper diye gaye ENV variables ke input fields banayein (Mainly: `BOT_TOKEN`, `BOT_USERNAME`, `OWNER_USERNAME`, `SUPPORT_CHAT`, `SUPPORT_CHANNEL`, `STRING_SESSION`, `MONGO_DB_URI`, `START_IMG_URL`).
2. **Environment Variable Injection**: User jab form submit kare, toh ye saare environment variables user ke container / instance me pass kar dein.
3. **Automatic Customization**: Jab bot start hoga, wo runtime pe saari environment variables padhega aur user ke brand name, support links, aur images buttons aur messages me display kar dega.

---

## ⚙️ Local / VPS Deployment Guide

### Command Line Deployment:

1. Clone repo & navigate into directory:
```bash
git clone https://github.com/spicycodez/DeluluMusic.git
cd DeluluMusic
```

2. Copy sample environment file & edit values:
```bash
cp sample.env .env
nano .env
```

3. Install dependencies & run:
```bash
pip install -r requirements.txt
python3 -m SONALI_MUSIC
```

---

## 🛠️ Developer & API Configurations

- `JIOSAAVN_API_URL`: `https://jiosaavn-a.kvinit6421.workers.dev/api/search/songs`
- `SPOTIFY_CLIENT_ID`: Custom Spotify Client ID
- `SPOTIFY_CLIENT_SECRET`: Custom Spotify Client Secret
