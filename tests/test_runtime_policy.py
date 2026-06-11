"""Per-turn caveman policy resolution from matched skills (src/runtime_policy)."""
import src.runtime_policy as rp


def _sk(name, *tags):
    return {"name": name, "tags": list(tags)}


def test_off_tag_disables():
    p = rp.resolve_from_skills([_sk("code", "caveman-off")])
    assert p and p["disabled"] is True


def test_off_wins_over_level():
    # A precision situation must win even if another match wants max compression.
    p = rp.resolve_from_skills([_sk("a", "caveman-caveman"), _sk("b", "caveman-off")])
    assert p["disabled"] is True


def test_strongest_level_chosen():
    p = rp.resolve_from_skills([_sk("a", "caveman-structural"), _sk("b", "caveman-caveman")])
    assert p["level"] == "caveman" and not p["disabled"]


def test_terse_is_additive():
    p = rp.resolve_from_skills([_sk("a", "caveman-terse")])
    assert p["terse"] is True and p["level"] is None and not p["disabled"]


def test_colon_and_hyphen_forms_both_parse():
    assert rp.resolve_from_skills([_sk("a", "caveman:off")])["disabled"] is True
    assert rp.resolve_from_skills([_sk("a", "caveman-off")])["disabled"] is True


def test_explicit_caveman_frontmatter_field():
    assert rp.resolve_from_skills([{"name": "a", "caveman": "off"}])["disabled"] is True


def test_no_policy_returns_none():
    assert rp.resolve_from_skills([_sk("a", "git", "github")]) is None
    assert rp.resolve_from_skills([]) is None
    assert rp.resolve_from_skills(None) is None


def test_contextvar_set_get_clear():
    rp.set_caveman_policy({"disabled": True, "level": None, "terse": False, "source": "x"})
    assert rp.get_caveman_policy()["disabled"] is True
    rp.clear_caveman_policy()
    assert rp.get_caveman_policy() is None
