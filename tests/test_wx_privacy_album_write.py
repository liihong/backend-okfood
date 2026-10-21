"""相册（仅写入）隐私项合并。

更新已授权小程序的开发版隐私指引（需平台管理员 Token，且该租户已代授权）：

curl -sS -X POST "http://127.0.0.1:8000/api/admin/system/tenants/3/wx-code/sync-album-write-privacy" \\
  -H "Authorization: Bearer $ADMIN_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d "{}"

查询开发版当前指引：

curl -sS "http://127.0.0.1:8000/api/admin/system/tenants/3/wx-code/privacy-setting?privacy_ver=2" \\
  -H "Authorization: Bearer $ADMIN_TOKEN"
"""

from app.services.shared.wx_open_code_service import (
    ALBUM_WRITE_ONLY_PRIVACY_KEY,
    ALBUM_WRITE_ONLY_PRIVACY_TEXT,
    DEFAULT_PRIVACY_SETTING_LIST,
    merge_album_write_only_privacy,
)


def test_default_template_includes_album_write_once() -> None:
    keys = [item["privacy_key"] for item in DEFAULT_PRIVACY_SETTING_LIST]
    assert keys == ["PhoneNumber", "Location", "ChooseLocation", "UserInfo", ALBUM_WRITE_ONLY_PRIVACY_KEY]
    assert "核销二维码" in ALBUM_WRITE_ONLY_PRIVACY_TEXT
    assert "分享海报" in ALBUM_WRITE_ONLY_PRIVACY_TEXT
    assert "不会读取" in ALBUM_WRITE_ONLY_PRIVACY_TEXT
    assert not ALBUM_WRITE_ONLY_PRIVACY_TEXT.startswith("用于")


def test_merge_keeps_other_purposes_and_overwrites_album() -> None:
    merged, used_default = merge_album_write_only_privacy(
        [
            {"privacy_key": "PhoneNumber", "privacy_text": "自定义手机号用途"},
            {"privacy_key": "AlbumWriteOnly", "privacy_text": "旧文案"},
            {"privacy_key": "Clipboard", "privacy_text": ""},
        ]
    )
    assert used_default is False
    assert [item["privacy_key"] for item in merged] == ["PhoneNumber", "AlbumWriteOnly"]
    assert merged[0]["privacy_text"] == "自定义手机号用途"
    assert merged[1]["privacy_text"] == ALBUM_WRITE_ONLY_PRIVACY_TEXT


def test_merge_empty_falls_back_to_okfood_template() -> None:
    merged, used_default = merge_album_write_only_privacy(None)
    assert used_default is True
    assert [item["privacy_key"] for item in merged] == [
        item["privacy_key"] for item in DEFAULT_PRIVACY_SETTING_LIST
    ]
    assert merged[-1]["privacy_text"] == ALBUM_WRITE_ONLY_PRIVACY_TEXT
