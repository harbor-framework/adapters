import pytest

from agentclinic.main import main


def test_cli_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--output-dir", "--limit", "--overwrite", "--task-ids", "--split"):
        assert flag in out


def test_split_rejects_unknown_value():
    with pytest.raises(SystemExit) as exc:
        main(["--split", "nejm"])
    assert exc.value.code == 2
