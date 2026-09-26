import os
import asyncio
import pytest
from SONALI_MUSIC.utils.youtube_utils import (
    get_cookie_files,
    get_valid_cookie_files,
    get_next_cookie_file,
    mark_cookie_unusable,
    is_cookie_usable,
    _UNUSABLE_COOKIES,
    _NOTIFIED_EXPIRED_COOKIES,
)


def test_multi_cookie_scanning():
    os.makedirs("cookies", exist_ok=True)
    dummy1 = os.path.join("cookies", "test_cookie_1.txt")
    dummy2 = os.path.join("cookies", "test_cookie_2.txt")

    content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\tSID\ttest_sid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\tSSID\ttest_ssid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\tSAPISID\ttest_sapisid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\t__Secure-1PSID\ttest_1psid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\t__Secure-3PSID\ttest_3psid_1\n"
    )

    with open(dummy1, "w", encoding="utf-8") as f:
        f.write(content)
    with open(dummy2, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        files = get_cookie_files()
        assert os.path.abspath(dummy1) in files
        assert os.path.abspath(dummy2) in files

        valid = get_valid_cookie_files()
        assert os.path.abspath(dummy1) in valid
        assert os.path.abspath(dummy2) in valid
    finally:
        if os.path.exists(dummy1):
            os.remove(dummy1)
        if os.path.exists(dummy2):
            os.remove(dummy2)


def test_cookie_rotation():
    os.makedirs("cookies", exist_ok=True)
    dummy1 = os.path.join("cookies", "test_rot_1.txt")
    dummy2 = os.path.join("cookies", "test_rot_2.txt")

    content = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\tSID\ttest_sid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\tSSID\ttest_ssid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\tSAPISID\ttest_sapisid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\t__Secure-1PSID\ttest_1psid_1\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1824970730\t__Secure-3PSID\ttest_3psid_1\n"
    )

    with open(dummy1, "w", encoding="utf-8") as f:
        f.write(content)
    with open(dummy2, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        c1 = get_next_cookie_file()
        c2 = get_next_cookie_file()
        assert c1 is not None
        assert c2 is not None
        # Verify rotation yields usable files
        assert is_cookie_usable(c1)
        assert is_cookie_usable(c2)
    finally:
        if os.path.exists(dummy1):
            os.remove(dummy1)
        if os.path.exists(dummy2):
            os.remove(dummy2)


@pytest.mark.asyncio
async def test_mark_cookie_unusable_and_notification():
    dummy = os.path.join("cookies", "test_expired.txt")
    with open(dummy, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")

    try:
        abs_p = os.path.abspath(dummy)
        mark_cookie_unusable(abs_p, reason="Test cookie expired")
        assert not is_cookie_usable(abs_p)
        assert abs_p in _UNUSABLE_COOKIES
    finally:
        if os.path.exists(dummy):
            os.remove(dummy)
