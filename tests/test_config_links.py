import os
import pytest
import config
from SONALI_MUSIC.help.buttons import BUTTONS
from SONALI_MUSIC.help.helper import Helper

def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("SUPPORT_CHAT", "https://t.me/CustomSupportChat")
    monkeypatch.setenv("SUPPORT_CHANNEL", "https://t.me/CustomSupportChannel")
    monkeypatch.setenv("BOT_NAME", "Test Custom Bot")
    monkeypatch.setenv("OWNER_USERNAME", "CustomOwner")
    monkeypatch.setenv("START_IMG_URL", "https://example.com/custom_start.jpg")

    # Reload config values
    import importlib
    import config
    importlib.reload(config)

    assert config.SUPPORT_CHAT == "https://t.me/CustomSupportChat"
    assert config.SUPPORT_CHANNEL == "https://t.me/CustomSupportChannel"
    assert config.BOT_NAME == "Test Custom Bot"
    assert config.OWNER_USERNAME == "CustomOwner"
    assert config.START_IMG_URL == "https://example.com/custom_start.jpg"

def test_buttons_and_helper_dynamic_links(monkeypatch):
    monkeypatch.setenv("SUPPORT_CHAT", "https://t.me/TestGroup")
    monkeypatch.setenv("SUPPORT_CHANNEL", "https://t.me/TestChannel")
    monkeypatch.setenv("OWNER_USERNAME", "TestOwnerHandle")
    monkeypatch.setenv("BOT_NAME", "Dynamic Bot Name")

    import importlib
    import config
    importlib.reload(config)

    import SONALI_MUSIC.help.buttons as buttons_mod
    import SONALI_MUSIC.help.helper as helper_mod
    importlib.reload(buttons_mod)
    importlib.reload(helper_mod)

    # Check ABUTTON
    abutton = buttons_mod.BUTTONS.ABUTTON
    assert abutton[0][0].url == "https://t.me/TestGroup"
    assert abutton[0][1].url == "https://t.me/TestChannel"

    # Check Helper ABOUT and ALLBOT
    helper_inst = helper_mod.Helper
    assert "https://t.me/TestChannel" in helper_inst.HELP_01
    assert "https://t.me/TestGroup" in helper_inst.HELP_PROMOTION
    assert "https://t.me/TestOwnerHandle" in helper_inst.HELP_ALLBOT
