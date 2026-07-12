import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from token_tool import set_env_key


def test_set_env_key_updates_existing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("A=1\nINSTAGRAM_ACCESS_TOKEN=old\nB=2\n", encoding="utf-8")
    set_env_key(f, "INSTAGRAM_ACCESS_TOKEN", "newtoken")
    lines = f.read_text(encoding="utf-8").splitlines()
    assert "INSTAGRAM_ACCESS_TOKEN=newtoken" in lines
    assert "A=1" in lines and "B=2" in lines
    assert "INSTAGRAM_ACCESS_TOKEN=old" not in lines


def test_set_env_key_appends_missing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("A=1\n", encoding="utf-8")
    set_env_key(f, "NEW_KEY", "value")
    assert "NEW_KEY=value" in f.read_text(encoding="utf-8").splitlines()


def test_set_env_key_preserves_comments(tmp_path):
    f = tmp_path / ".env"
    f.write_text("# 주석\nA=1\n", encoding="utf-8")
    set_env_key(f, "A", "2")
    text = f.read_text(encoding="utf-8")
    assert "# 주석" in text
    assert "A=2" in text.splitlines()
