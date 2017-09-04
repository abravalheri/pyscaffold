#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
import sys

import pytest

from pyscaffold import cli
from pyscaffold.exceptions import OldSetuptools
from pyscaffold.log import logger

from .log_helpers import ansi_regex, find_report

__author__ = "Florian Wilhelm"
__copyright__ = "Blue Yonder"
__license__ = "new BSD"


@pytest.fixture
def fake_home(tmpfolder, monkeypatch):
    fake_home = tmpfolder.ensure_dir('fake-home')
    monkeypatch.setenv('HOME', str(fake_home))
    yield fake_home


@pytest.fixture
def fake_osx(fake_home, monkeypatch):
    fake_home.ensure_dir('Library', 'Application Support')
    yield


def test_get_config_on_osx(fake_osx):
    assert (cli.get_config_dir().replace(os.sep, '/') == os.path.expandvars(
            '${HOME}/Library/Application Support/pyscaffold'))


@pytest.fixture
def fake_windows(fake_home, monkeypatch):
    config = fake_home.ensure_dir('AppData', 'Roaming')
    monkeypatch.setenv('USERPROFILE', str(fake_home))
    monkeypatch.setenv('APPDATA', str(config))
    yield


def test_get_config_on_windows(fake_windows):
    assert (cli.get_config_dir().replace(os.sep, '/') ==
            os.path.expandvars('${USERPROFILE}/AppData/Roaming/pyscaffold'))


@pytest.fixture
def fake_unix(fake_home, monkeypatch):
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    fake_home.ensure_dir('.config')
    yield


def test_get_config_on_unix(fake_unix):
    assert (cli.get_config_dir().replace(os.sep, '/') ==
            os.path.expandvars('${HOME}/.config/pyscaffold'))


@pytest.fixture
def fake_unknown_os(fake_home, monkeypatch):
    monkeypatch.delenv('HOME', raising=False)
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    monkeypatch.setattr('os.path.expanduser',
                        lambda x: x.replace('~', str(fake_home)))
    yield


def test_get_config_on_unknown_os(fake_unknown_os):
    assert (cli.get_config_dir().replace(os.sep, '/') ==
            os.path.expanduser('~/.pyscaffold'))


def test_get_config_with_xdg(fake_unix, tmpfolder, monkeypatch):
    config = tmpfolder.ensure_dir('xdg-config')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(config))
    assert (
        cli.get_config_dir()
        .replace(os.sep, '/')
        .endswith('xdg-config/pyscaffold')
    )


def test_args_file(fake_unix):
    filename = cli.get_args_file('foobar')
    assert (filename.replace(os.sep, '/') ==
            os.path.expandvars('${HOME}/.config/pyscaffold/foobar.args'))
    filename = cli.get_args_file(None)
    assert (filename.replace(os.sep, '/') ==
            os.path.expandvars('${HOME}/.config/pyscaffold/default.args'))


def test_parse_args():
    args = ["my-project"]
    opts = cli.parse_args(args)
    assert opts['project'] == "my-project"


def test_parse_args_with_old_setuptools(old_setuptools_mock):  # noqa
    args = ["my-project"]
    with pytest.raises(OldSetuptools):
        cli.parse_args(args)


def test_parse_quiet_option():
    for quiet in ("--quiet", "-q"):
        args = ["my-project", quiet]
        opts = cli.parse_args(args)
        assert opts["log_level"] == logging.CRITICAL


def test_parse_default_log_level():
    args = ["my-project"]
    opts = cli.parse_args(args)
    assert opts["log_level"] == logging.INFO


def test_parse_pretend():
    for flag in ["--pretend", "--dry-run"]:
        opts = cli.parse_args(["my-project", flag])
        assert opts["pretend"]
    opts = cli.parse_args(["my-project"])
    assert not opts["pretend"]


def test_parse_list_actions():
    opts = cli.parse_args(["my-project", "--list-actions"])
    assert opts["command"] == cli.list_actions
    opts = cli.parse_args(["my-project"])
    assert opts["command"] == cli.run_scaffold


def test_main(tmpfolder, git_mock, caplog):  # noqa
    args = ["my-project"]
    cli.main(args)
    assert os.path.exists(args[0])

    # Check for some log messages
    assert find_report(caplog, 'invoke', 'get_default_options')
    assert find_report(caplog, 'invoke', 'verify_options_consistency')
    assert find_report(caplog, 'invoke', 'define_structure')
    assert find_report(caplog, 'invoke', 'create_structure')
    assert find_report(caplog, 'create', 'setup.py')
    assert find_report(caplog, 'create', 'requirements.txt')
    assert find_report(caplog, 'create', 'my_project/__init__.py')
    assert find_report(caplog, 'run', 'git init')
    assert find_report(caplog, 'run', 'git add')


def test_pretend_main(tmpfolder, git_mock, caplog):  # noqa
    for flag in ["--pretend", "--dry-run"]:
        args = ["my-project", flag]
        cli.main(args)
        assert not os.path.exists(args[0])

        # Check for some log messages
        assert find_report(caplog, 'invoke', 'get_default_options')
        assert find_report(caplog, 'invoke', 'verify_options_consistency')
        assert find_report(caplog, 'invoke', 'define_structure')
        assert find_report(caplog, 'invoke', 'create_structure')
        assert find_report(caplog, 'create', 'setup.py')
        assert find_report(caplog, 'create', 'requirements.txt')
        assert find_report(caplog, 'create', 'my_project/__init__.py')
        assert find_report(caplog, 'run', 'git init')
        assert find_report(caplog, 'run', 'git add')


def test_main_when_updating(tmpfolder, capsys, git_mock):  # noqa
    args = ["my-project"]
    cli.main(args)
    args = ["--update", "my-project"]
    cli.main(args)
    assert os.path.exists(args[1])
    out, _ = capsys.readouterr()
    assert "Update accomplished!" in out


def test_main_with_list_actions(capsys, reset_logger):
    # When putup is called with --list-actions,
    args = ["my-project", "--with-tox", "--list-actions"]
    cli.main(args)
    # then the action list should be printed,
    out, _ = capsys.readouterr()
    assert "Planned Actions" in out
    assert "pyscaffold.api:get_default_options" in out
    assert "pyscaffold.structure:define_structure" in out
    assert "pyscaffold.extensions.tox:add_files" in out
    assert "pyscaffold.structure:create_structure" in out
    assert "pyscaffold.api:init_git" in out
    # but no project should be created
    assert not os.path.exists(args[0])


def create_args_file(folder, name='default.args'):
    fh = folder.join(name)
    fh.write(
        "--license mozilla\n"  # check multiple args per line
        "--description 'My Project Description'\n"  # check quotes
        "--with-pre-commit # A comment\n"  # check trailing comments
        "--with-tox\n"
        "# Another comment\n"  # check line comments
        "--with-travis\n")
    return fh


def test_main_with_file(tmpfolder):
    # Given a pyscaffold.args file exists in the current directory,
    create_args_file(tmpfolder, 'pyscaffold.args')
    # when main is called with that file,
    args = ["my-project", "@pyscaffold.args"]
    cli.main(args)
    # then extra options should be read from it
    assert tmpfolder.join("my-project/.pre-commit-config.yaml").check()
    assert tmpfolder.join("my-project/tox.ini").check()
    assert tmpfolder.join("my-project/.travis.yml").check()
    assert "Mozilla" in tmpfolder.join("my-project/LICENSE.txt").read()
    assert ("summary = My Project Description" in
            tmpfolder.join("my-project/setup.cfg").read())


@pytest.fixture
def fake_config_dir(fake_unix, fake_home):
    config = fake_home.ensure_dir('.config', 'pyscaffold')
    gitconfig = (
        "[user]\n"
        "\tname = Your Name\n"
        "\temail = you@example.com\n")
    fake_home.ensure_dir('.config', 'git').join('config').write(gitconfig)
    fake_home.join('.gitconfig').write(gitconfig)  # older versions of git
    yield config


def test_main_with_default_profile(fake_config_dir, tmpfolder):
    # Given a default.args file exists in the config directory,
    create_args_file(fake_config_dir, 'default.args')
    # when main is called,
    args = ["my-project"]
    cli.main(args)
    # then extra options should be read from it
    assert tmpfolder.join("my-project/.pre-commit-config.yaml").check()
    assert tmpfolder.join("my-project/tox.ini").check()
    assert tmpfolder.join("my-project/.travis.yml").check()
    assert "Mozilla" in tmpfolder.join("my-project/LICENSE.txt").read()
    assert ("summary = My Project Description" in
            tmpfolder.join("my-project/setup.cfg").read())


def test_main_with_profile(fake_config_dir, monkeypatch, tmpfolder):
    # Given a ${PYSCAFFOLD_PROFILE}.args file exists in the config directory,
    monkeypatch.setenv('PYSCAFFOLD_PROFILE', 'foo')
    create_args_file(fake_config_dir, 'bar.args')
    fake_config_dir.join('foo.args').write(
        '@{}/bar.args'.format(fake_config_dir))
    #   ^   take the opportunity to also test file arguments in files
    # when main is called,
    args = ["my-project"]
    cli.main(args)
    # then extra options should be read from it
    assert tmpfolder.join("my-project/.pre-commit-config.yaml").check()
    assert tmpfolder.join("my-project/tox.ini").check()
    assert tmpfolder.join("my-project/.travis.yml").check()
    assert "Mozilla" in tmpfolder.join("my-project/LICENSE.txt").read()
    assert ("summary = My Project Description" in
            tmpfolder.join("my-project/setup.cfg").read())


def test_main_without_profile(fake_config_dir, monkeypatch, tmpfolder):
    # Given files default.args and none.args exist in the config directory,
    create_args_file(fake_config_dir, 'default.args')
    create_args_file(fake_config_dir, 'none.args')
    # and ${PYSCAFFOLD_PROFILE} is none,
    monkeypatch.setenv('PYSCAFFOLD_PROFILE', 'none')
    # when main is called,
    args = ["my-project"]
    cli.main(args)
    # then no extra options should be read
    assert not tmpfolder.join("my-project/.pre-commit-config.yaml").check()
    assert not tmpfolder.join("my-project/tox.ini").check()
    assert not tmpfolder.join("my-project/.travis.yml").check()
    assert "Mozilla" not in tmpfolder.join("my-project/LICENSE.txt").read()
    assert ("summary = My Project Description" not in
            tmpfolder.join("my-project/setup.cfg").read())


def test_run(tmpfolder, git_mock):  # noqa
    sys.argv = ["pyscaffold", "my-project"]
    cli.run()
    assert os.path.exists(sys.argv[1])


def test_configure_logger(monkeypatch, caplog, reset_logger):
    # Given an environment that supports color,
    monkeypatch.setattr('pyscaffold.termui.supports_color', lambda *_: True)
    # when configure_logger in called,
    opts = dict(log_level=logging.INFO)
    cli.configure_logger(opts)
    # then the formatter should be changed to use colors,
    logger.report('some', 'activity')
    out = caplog.text
    assert ansi_regex('some').search(out)
