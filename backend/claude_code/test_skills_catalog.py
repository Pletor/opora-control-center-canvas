from backend.claude_code.skills_catalog import list_skills, parse_frontmatter


def skill(root, name, description, folder=None):
    folder = root / (folder or name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n", encoding="utf-8")


def test_frontmatter_reads_flat_keys_and_strips_quotes():
    text = '---\nname: graphify\ndescription: "Knowledge graph"\nmetadata:\n  type: x\n---\n# body\ndescription: not this\n'
    assert parse_frontmatter(text) == {"name": "graphify", "description": "Knowledge graph", "metadata": ""}
    assert parse_frontmatter("# no frontmatter") == {}


def test_frontmatter_joins_block_scalars():
    text = "---\nname: caveman\ndescription: >\n  Ultra-compressed mode.\n  Cuts tokens.\n\n  Keeps accuracy.\nmetadata:\n  type: x\n---\n"
    meta = parse_frontmatter(text)
    assert meta["description"] == "Ultra-compressed mode. Cuts tokens. Keeps accuracy."
    assert meta["name"] == "caveman"


def test_lists_project_user_and_plugin_skills_in_that_order(tmp_path):
    project = tmp_path / "repo/.claude/skills"
    user = tmp_path / "home/.claude/skills"
    plugins = tmp_path / "home/.claude/plugins/marketplaces"
    skill(project, "opora-control-center", "Ovládá OPORA Canvas.")
    skill(user, "graphify", "Knowledge graph.")
    skill(plugins / "vercel", "nextjs", "Next.js guidance.", folder="skills/nextjs")
    skill(plugins / "wozcode", "woz-recall", "Recall sessions.", folder="plugins/woz/skills/woz-recall")
    (user / "broken").mkdir()
    (user / "broken/README.md").write_text("no skill", encoding="utf-8")

    items = list_skills({"project": project, "user": user, "plugins": plugins})

    assert [item["id"] for item in items] == [
        "project:opora-control-center",
        "user:graphify",
        "plugin:vercel:nextjs",
        "plugin:wozcode:woz-recall",
    ]
    assert items[0]["description"] == "Ovládá OPORA Canvas."
    assert items[2]["scope"] == "plugin:vercel"
    assert items[3]["path"].endswith("woz-recall")


def test_missing_roots_and_long_descriptions_are_safe(tmp_path):
    user = tmp_path / "skills"
    skill(user, "long", "x" * 500)
    items = list_skills({"project": tmp_path / "missing", "user": user, "plugins": tmp_path / "nope"})
    assert len(items) == 1
    assert len(items[0]["description"]) == 300
    assert items[0]["description"].endswith("…")
