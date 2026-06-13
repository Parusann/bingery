"""Guards on the Render deploy config so the production-safety regressions
the review found can't silently come back."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_build_sh_does_not_seed():
    """build.sh runs on every Render deploy; it must not invoke seed.py
    (which drops all tables). Comments mentioning it are fine."""
    code_lines = [
        ln for ln in _read("build.sh").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert not any("seed.py" in ln for ln in code_lines)


def test_render_web_service_enables_production_guards():
    """The web service must run with FLASK_ENV=production so the config
    boot guards activate instead of being bypassed."""
    content = _read("render.yaml")
    assert "FLASK_ENV" in content
    assert "production" in content


def test_render_declares_required_production_vars():
    """Production refuses to boot without these — they must be declared so
    the service doesn't crash-loop."""
    content = _read("render.yaml")
    for key in ("SECRET_KEY", "CORS_ORIGINS", "EMAIL_PROVIDER", "BREVO_API_KEY", "EMAIL_FROM"):
        assert key in content, f"render.yaml missing {key}"
