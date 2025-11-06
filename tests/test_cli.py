from importlib.metadata import version

from typer.testing import CliRunner

from primal_page.main import app

runner = CliRunner()

# This uses pytest rather than unittest
# Run using: poetry run pytest


# Test the app can run with the version flag
def test_app_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert version("primal-page") in result.stdout
