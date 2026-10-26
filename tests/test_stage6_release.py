"""6단계: 업데이트 확인, 설정 호환성, 포터블 모드."""
import io
import json

from ellview import __version__
from ellview.config import DEFAULTS, Settings
from ellview.core import updater


def test_version_compare():
    assert updater.is_newer("0.2.0", "0.1.9")
    assert updater.is_newer("v1.0", "0.9.9")
    assert not updater.is_newer("0.1.0", "0.1.0")
    assert not updater.is_newer("0.0.9", __version__)


def test_fetch_latest_parses(monkeypatch):
    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    payload = {"tag_name": "v9.9.9", "html_url": "https://example/rel", "body": "notes"}
    monkeypatch.setattr(updater.urllib.request, "urlopen", lambda *a, **k: R(json.dumps(payload).encode()))
    info = updater.fetch_latest("me/Ellview")
    assert info == {"version": "9.9.9", "url": "https://example/rel", "notes": "notes"}
    assert updater.fetch_latest("") is None


def test_settings_forward_compatible(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"fit_mode": "width", "unknown_old_key": 1}), encoding="utf-8")
    s = Settings(p)
    assert s["fit_mode"] == "width"
    assert s["boundary_action"] == DEFAULTS["boundary_action"], "새로 생긴 설정은 기본값"
    s.save()
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert "unknown_old_key" not in saved and saved["schema"] == DEFAULTS["schema"]


def test_corrupt_settings_fallback(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{broken", encoding="utf-8")
    assert Settings(p)["fit_mode"] == DEFAULTS["fit_mode"]


def test_portable_mode(tmp_path, monkeypatch):
    import ellview.config as cfg
    monkeypatch.delenv("ELLVIEW_DATA_DIR", raising=False)
    monkeypatch.setattr(cfg, "app_base_dir", lambda: tmp_path)
    (tmp_path / "portable.txt").write_text("")
    assert cfg.data_dir() == tmp_path / "data"
