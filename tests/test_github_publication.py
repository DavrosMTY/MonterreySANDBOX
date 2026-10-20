import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import publish_github as publish


def test_pr_reuses_existing_request_and_does_not_create_another(monkeypatch):
    calls=[]
    def invoke(args,check=True):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps([{'url':'https://github.com/DavrosMTY/MonterreySANDBOX/pull/1'}]),returncode=0)
    monkeypatch.setattr(publish,'invoke',invoke)
    result=publish.pull_request(Path('body.md'))
    assert result['status']=='existing'
    assert len(calls)==1 and calls[0][:2]==['pr','list']


def test_new_pr_targets_main_from_development_and_never_merges(monkeypatch):
    calls=[]
    def invoke(args,check=True):
        calls.append(args)
        return SimpleNamespace(stdout='[]' if args[1]=='list' else 'https://github.com/DavrosMTY/MonterreySANDBOX/pull/2\n',returncode=0)
    monkeypatch.setattr(publish,'invoke',invoke)
    assert publish.pull_request(Path('body.md'))['status']=='created'
    command=calls[-1]
    assert command[command.index('--base')+1]=='main'
    assert command[command.index('--head')+1]=='development'
    assert '--body-file' in command
    assert all('merge' not in call for call in calls)


def test_release_refuses_to_replace_existing_assets(tmp_path,monkeypatch):
    (tmp_path/'release-manifest.json').write_text(json.dumps({'source_commit':'a'*40,'files':[]}))
    calls=[]
    def invoke(args,check=True):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps({'isPrivate':False}) if args[0]=='repo' else '{}',stderr='',returncode=0)
    monkeypatch.setattr(publish,'invoke',invoke)
    with pytest.raises(RuntimeError,match='already exists'):publish.release(tmp_path)
    assert all('create' not in call and 'upload' not in call for call in calls)


def test_release_does_not_treat_permission_denial_as_missing_release(tmp_path,monkeypatch):
    (tmp_path/'release-manifest.json').write_text(json.dumps({'source_commit':'b'*40,'files':[]}))
    calls=[]
    def invoke(args,check=True):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps({'isPrivate':False}),stderr='HTTP 403: access denied',returncode=0 if args[0]=='repo' else 1)
    monkeypatch.setattr(publish,'invoke',invoke)
    with pytest.raises(RuntimeError,match='403'):publish.release(tmp_path)
    assert all('create' not in call for call in calls)
