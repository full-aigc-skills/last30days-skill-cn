"""回归测试：保证可安装的 SKILL 载荷入口是普通文件而非损坏的 symlink。

背景见 issue #10：skills/last30days-cn/SKILL.md 曾被以 symlink 模式（120000）提交，
但 blob 内容是完整 SKILL 正文，导致 macOS/Linux clone 时报 "File name too long"。
"""

import os
import subprocess
import sys
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL_ENTRY = os.path.join(REPO_ROOT, "skills", "last30days-cn", "SKILL.md")


def test_skill_entry_is_regular_file_not_symlink():
    assert os.path.exists(SKILL_ENTRY), "skills/last30days-cn/SKILL.md 缺失"
    assert not os.path.islink(SKILL_ENTRY), "SKILL.md 不应是 symlink（见 issue #10）"


def test_skill_entry_has_frontmatter():
    with open(SKILL_ENTRY, "r", encoding="utf-8") as f:
        content = f.read()
    assert content.strip(), "SKILL.md 不应为空"
    assert "name:" in content, "SKILL.md 应包含 Agent Skill frontmatter"


def test_skill_documents_output_contract_and_cache_flags():
    with open(os.path.join(REPO_ROOT, "SKILL.md"), "r", encoding="utf-8") as f:
        content = f.read()
    for needle in ("输出契约", "--refresh", "--no-cache", "setup", "查询类型"):
        assert needle in content


def test_payload_matches_root_sources():
    result = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "build_payload.py"), "--check"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_payload_preserves_codex_metadata_on_repeated_sync():
    """Codex 配置必须随源文件打包，重复同步不能将其作为孤立文件删除。"""
    namespace = runpy.run_path(os.path.join(REPO_ROOT, "scripts", "build_payload.py"))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        payload = root / "skills" / "last30days-cn"
        (root / "scripts").mkdir()
        (root / "agents").mkdir()
        (root / "SKILL.md").write_text("---\nname: last30days-cn\n---\n", encoding="utf-8")
        metadata = root / "agents" / "openai.yaml"
        metadata.write_text('interface:\n  display_name: "近30天研究"\n', encoding="utf-8")
        globals_for_sync = namespace["sync"].__globals__
        with patch.dict(globals_for_sync, {
            "ROOT": root, "PAYLOAD": payload,
            "SOURCE_SKILL": root / "SKILL.md", "PAYLOAD_SKILL": payload / "SKILL.md",
            "SOURCE_SCRIPTS": root / "scripts", "PAYLOAD_SCRIPTS": payload / "scripts",
            "SOURCE_AGENTS": root / "agents", "PAYLOAD_AGENTS": payload / "agents",
        }):
            for _ in range(2):
                assert namespace["sync"]() == 0
                installed = payload / "agents" / "openai.yaml"
                assert installed.is_file(), "打包同步遗漏了 agents/openai.yaml"
                assert installed.read_bytes() == metadata.read_bytes()
                assert namespace["check"]() == 0
