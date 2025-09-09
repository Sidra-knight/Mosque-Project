# github_tools.py — small wrappers around GitHub Contents & Template APIs
import os
import base64
import json
import requests
from typing import Optional

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API = 'https://api.github.com'
GITHUB_ORG = os.getenv('GITHUB_ORG')
DEFAULT_BRANCH = os.getenv('DEFAULT_BRANCH', 'main')

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}


class GitHubError(Exception):
    pass


def slugify(name: str) -> str:
    s = name.lower().strip()
    for ch in " _/\\":
        s = s.replace(ch, '-')
    # collapse multiple dashes
    while '--' in s:
        s = s.replace('--', '-')
    return s


def create_repo_from_template(template_owner: str, template_repo: str, new_name: str, owner: Optional[str] = None):
    url = f"{GITHUB_API}/repos/{template_owner}/{template_repo}/generate"
    payload = {"name": new_name}
    if owner:
        payload['owner'] = owner
    r = requests.post(url, json=payload, headers=HEADERS)
    if r.status_code not in (201, 202):
        raise GitHubError(f'Create-from-template failed: {r.status_code} {r.text}')
    return r.json()


def _get_file(owner: str, repo: str, path: str):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=HEADERS, params={'ref': DEFAULT_BRANCH})
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        return None
    raise GitHubError(f'Get file failed: {r.status_code} {r.text}')


def write_json(owner: str, repo: str, path: str, data: dict, message: str):
    content_b64 = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    existing = _get_file(owner, repo, path)
    payload = {
        'message': message,
        'content': content_b64,
        'branch': DEFAULT_BRANCH
    }
    if existing:
        payload['sha'] = existing['sha']
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.put(url, json=payload, headers=HEADERS)
    if r.status_code not in (200,201):
        raise GitHubError(f'Write JSON failed: {r.status_code} {r.text}')
    return r.json()


def put_file(owner: str, repo: str, path: str, raw_bytes: bytes, message: str):
    content_b64 = base64.b64encode(raw_bytes).decode()
    existing = _get_file(owner, repo, path)
    payload = {
        'message': message,
        'content': content_b64,
        'branch': DEFAULT_BRANCH
    }
    if existing:
        payload['sha'] = existing['sha']
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    r = requests.put(url, json=payload, headers=HEADERS)
    if r.status_code not in (200,201):
        raise GitHubError(f'Put file failed: {r.status_code} {r.text}')
    return r.json()


def read_json(owner: str, repo: str, path: str):
    obj = _get_file(owner, repo, path)
    if not obj:
        return None
    content = base64.b64decode(obj['content']).decode()
    return json.loads(content)


def get_commits(owner: str, repo: str, per_page: int = 20):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    r = requests.get(url, headers=HEADERS, params={'per_page': per_page})
    if r.status_code != 200:
        raise GitHubError(f'Get commits failed: {r.status_code} {r.text}')
    return r.json()
