from textwrap import dedent

from proxysql_cfgcheck import main


def test_cli_check_success(capsys) -> None:
    code = main(["check", "tests/data/minimal.cnf"])

    captured = capsys.readouterr()
    assert code == 0
    assert "OK" in captured.out


def test_cli_missing_file(capsys) -> None:
    code = main(["check", "tests/data/does-not-exist.cnf"])

    captured = capsys.readouterr()
    assert code == 2
    assert "File not found" in captured.err


def test_cli_warn_only_returns_success(tmp_path, capsys) -> None:
    config = tmp_path / "warn.cnf"
    config.write_text(
        dedent(
            """
            datadir="/tmp/proxysql"

            admin_variables={
                admin_credentials="admin:secret"
            }

            mysql_variables={}

            mysql_servers = (
                { address = "127.0.0.1", port = 3306, hostgroup = 0, max_connections = 100 }
            )
            """
        ).strip(),
        encoding="utf-8",
    )

    code = main(["check", str(config)])

    captured = capsys.readouterr()
    assert code == 0
    assert "WARNING" in captured.out


def test_cli_check_config_with_setting_terminators(tmp_path, capsys) -> None:
    config = tmp_path / "terminated.cnf"
    config.write_text(
        dedent(
            """
            datadir="/tmp/proxysql";
            admin_variables={
                admin_credentials="admin:secret;radmin:other";
                mysql_ifaces="127.0.0.1:6032";
            };
            mysql_variables={ threads=4; };
            mysql_servers=(
                { address="127.0.0.1"; port=3306; hostgroup=0; max_connections=200; }
            );
            """
        ),
        encoding="utf-8",
    )

    code = main(["check", str(config)])

    captured = capsys.readouterr()
    assert code == 0
    assert "OK" in captured.out
    assert captured.err == ""
