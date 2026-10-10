from pathlib import Path

import pytest

from proxysql_cfgcheck.config_loader import ConfigLoader
from proxysql_cfgcheck.config_parser import ConfigSyntaxError, parse_config


def test_parse_minimal_config(tmp_path: Path) -> None:
    fixture = Path("tests/data/minimal.cnf")
    data = fixture.read_text(encoding="utf-8")
    parsed = parse_config(data)

    assert parsed["datadir"] == "/var/lib/proxysql"
    assert parsed["admin_variables"]["admin_credentials"] == "admin:admin"
    assert parsed["mysql_servers"][0]["hostgroup"] == 0


def test_config_loader_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "config.cnf"
    path.write_text("datadir=\"/tmp/proxy\"", encoding="utf-8")

    loader = ConfigLoader(path)
    parsed = loader.load()

    assert parsed["datadir"] == "/tmp/proxy"


@pytest.mark.parametrize("terminator", ["", ",", ";"])
def test_parse_setting_terminators(terminator: str) -> None:
    text = (
        f'datadir="/tmp/proxysql"{terminator}\n'
        f'admin_variables={{\n'
        f'admin_credentials="admin:secret;radmin:other"{terminator}\n'
        f'mysql_ifaces="127.0.0.1:6032"{terminator}\n'
        f'}}{terminator}'
    )

    assert parse_config(text) == {
        "datadir": "/tmp/proxysql",
        "admin_variables": {
            "admin_credentials": "admin:secret;radmin:other",
            "mysql_ifaces": "127.0.0.1:6032",
        },
    }


def test_parse_setting_terminators_in_list_groups() -> None:
    text = """
        mysql_servers = (
            { address="127.0.0.1"; port=3306; hostgroup=0; },
            { address="127.0.0.2"; port=3307; hostgroup=0; }
        ); # terminated list setting
    """

    assert parse_config(text) == {
        "mysql_servers": [
            {"address": "127.0.0.1", "port": 3306, "hostgroup": 0},
            {"address": "127.0.0.2", "port": 3307, "hostgroup": 0},
        ]
    }


@pytest.mark.parametrize("text", ["values=(1;2)", "values=(1;)", "value=1;;"])
def test_reject_semicolons_outside_setting_terminators(text: str) -> None:
    with pytest.raises(ConfigSyntaxError):
        parse_config(text)
