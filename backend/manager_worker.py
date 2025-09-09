# manager_worker.py — Manager (LLM planner) and Worker (executor) glue
import os
import json
import base64
from datetime import datetime
from typing import Dict, Any

import openai
from .github_tools import (
    create_repo_from_template, write_json, put_file, read_json, get_commits, slugify,
    GITHUB_TEMPLATE_REPO, GITHUB_TEMPLATE_OWNER
)

# OpenAI init
openai.api_key = os.getenv('OPENAI_API_KEY')
MANAGER_MODEL = os.getenv('MANAGER_MODEL', 'gpt-4o')
WORKER_MODEL = os.getenv('WORKER_MODEL', 'gpt-4o-mini')

ALLOWED_ACTIONS = [
    'scaffold_site', 'add_announcement', 'update_config', 'set_jumuah',
    'set_eid', 'upload_image', 'edit_homepage_copy'
]

MANAGER_SYSTEM = '''You are MANAGER. Never run tools.
Output strict JSON ONLY with the shape: {"action": <one of ALLOWED_ACTIONS>, "args": {...}}
Choose the minimal single step that advances the user's instruction. If multiple things are asked, pick the first only.
Allowed actions: scaffold_site, add_announcement, update_config, set_jumuah, set_eid, upload_image, edit_homepage_copy.
Args must be as compact as possible and only include necessary fields. Dates: use ISO8601 or YYYY-MM-DD format when appropriate.
'''

WORKER_SYSTEM = 'You are WORKER. You must call exactly one tool and return a JSON status.'

# Worker tool wrappers — each wrapper may perform multiple GitHub API calls but is considered one tool invocation.

from .github_tools import GITHUB_ORG, GITHUB_TEMPLATE_OWNER, GITHUB_TEMPLATE_REPO


def manager_plan(instruction: str, context: Dict[str, Any]) -> Dict[str, Any]:
    # Compose messages
    messages = [
        {"role": "system", "content": MANAGER_SYSTEM},
        {"role": "user", "content": json.dumps({"instruction": instruction, "context": context})}
    ]
    resp = openai.ChatCompletion.create(model=MANAGER_MODEL, messages=messages, max_tokens=400)
    text = resp['choices'][0]['message']['content'].strip()
    # Enforce JSON parse — expect manager to output JSON only
    try:
        plan = json.loads(text)
    except Exception as e:
        raise ValueError(f'Manager did not return valid JSON: {e}\n{text}')
    if 'action' not in plan or 'args' not in plan:
        raise ValueError(f'Invalid plan from manager: {plan}')
    if plan['action'] not in ALLOWED_ACTIONS:
        raise ValueError(f'Action not allowed: {plan["action"]}')
    return plan


# Helper: merge manager args (source-of-truth) with provided context; manager wins.
def _merge_args(manager_args: dict, context: dict) -> dict:
    final = dict(context or {})
    final.update(manager_args or {})
    return final


# TOOL: scaffold_site

def tool_scaffold_site(args: dict):
    # args: {name, location, images?}
    name = args['name']
    location = args.get('location', '')
    images = args.get('images', []) or []

    slug = slugify(name)
    new_repo_name = slug
    # create repo from template
    created = create_repo_from_template(os.getenv('GITHUB_TEMPLATE_OWNER'), os.getenv('GITHUB_TEMPLATE_REPO'), new_repo_name, owner=os.getenv('GITHUB_ORG'))
    owner = os.getenv('GITHUB_ORG')
    repo = new_repo_name

    # parse lat,lon from location if possible
    lat = 0.0
    lon = 0.0
    if isinstance(location, str) and ',' in location:
        try:
            parts = location.split(',')
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except:
            lat = 0.0
            lon = 0.0

    now_iso = datetime.utcnow().isoformat() + 'Z'
    config = {
        "name": name,
        "address": location,
        "lat": lat,
        "lon": lon,
        "calc_method": 2,
        "school": 0,
        "theme": "default",
        "show_eid": False,
        "created_iso": now_iso
    }
    write_json(owner, repo, 'docs/content/config.json', config, 'chore: initialize config.json')
    write_json(owner, repo, 'docs/content/announcements.json', {"items": []}, 'chore: initialize announcements')
    write_json(owner, repo, 'docs/content/jumuah.json', {"entries": []}, 'chore: initialize jumuah')
    write_json(owner, repo, 'docs/content/eid.json', {"visible": False, "datetime": None}, 'chore: initialize eid')

    # upload images
    uploaded = []
    for img in images:
        filename = img.get('filename')
        b64 = img.get('b64')
        if filename and b64:
            raw = base64.b64decode(b64)
            path = f'docs/assets/images/{filename}'
            put_file(owner, repo, path, raw, f'feat: add image {filename}')
            uploaded.append(filename)

    return {"ok": True, "tool": "scaffold_site", "result": {"repo": f"{owner}/{repo}", "uploaded_images": uploaded, "created_repo": created}}


# TOOL: add_announcement

def tool_add_announcement(args: dict):
    owner = os.getenv('GITHUB_ORG')
    repo = args['repo_slug']
    text = args['text']
    start_at = args.get('start_at')
    end_at = args.get('end_at')
    image = args.get('image')

    ann = read_json(owner, repo, 'docs/content/announcements.json') or {"items": []}
    items = ann.get('items', [])

    entry = {"text": text}
    if start_at:
        entry['start_at'] = start_at
    if end_at:
        entry['end_at'] = end_at
    if image:
        # image: {filename, b64}
        filename = image['filename']
        raw = base64.b64decode(image['b64'])
        path = f'docs/assets/images/{filename}'
        put_file(owner, repo, path, raw, f'feat: add announcement image {filename}')
        entry['image'] = filename

    items.append(entry)
    # no complex sorting; write back
    write_json(owner, repo, 'docs/content/announcements.json', {"items": items}, 'feat: add announcement')
    return {"ok": True, "tool": "add_announcement", "result": entry}


# TOOL: update_config

def tool_update_config(args: dict):
    owner = os.getenv('GITHUB_ORG')
    repo = args['repo_slug']
    changes = args.get('changes', {})
    cfg = read_json(owner, repo, 'docs/content/config.json') or {}
    cfg.update(changes)
    write_json(owner, repo, 'docs/content/config.json', cfg, 'feat: update config')
    return {"ok": True, "tool": "update_config", "result": changes}


# TOOL: set_jumuah

def tool_set_jumuah(args: dict):
    owner = os.getenv('GITHUB_ORG')
    repo = args['repo_slug']
    friday_date = args['friday_date']
    khutbah_time = args['khutbah_time']
    prayer_time = args['prayer_time']

    j = read_json(owner, repo, 'docs/content/jumuah.json') or {"entries": []}
    entries = j.get('entries', [])
    # replace or append by date
    replaced = False
    for e in entries:
        if e.get('date') == friday_date:
            e['khutbah_time'] = khutbah_time
            e['prayer_time'] = prayer_time
            replaced = True
            break
    if not replaced:
        entries.append({"date": friday_date, "khutbah_time": khutbah_time, "prayer_time": prayer_time})
    # sort by date
    entries = sorted(entries, key=lambda x: x['date'])
    write_json(owner, repo, 'docs/content/jumuah.json', {"entries": entries}, f'feat: set jumuah {friday_date}')
    return {"ok": True, "tool": "set_jumuah", "result": {"date": friday_date}}


# TOOL: set_eid

def tool_set_eid(args: dict):
    owner = os.getenv('GITHUB_ORG')
    repo = args['repo_slug']
    visible = args.get('visible')
    datetime_val = args.get('datetime') if args.get('datetime') not in (None, '') else None
    e = read_json(owner, repo, 'docs/content/eid.json') or {"visible": False, "datetime": None}
    if visible is not None:
        e['visible'] = bool(visible)
    if datetime_val is not None:
        e['datetime'] = datetime_val
    write_json(owner, repo, 'docs/content/eid.json', e, 'feat: set eid')
    return {"ok": True, "tool": "set_eid", "result": e}


# TOOL: upload_image

def tool_upload_image(args: dict):
    owner = os.getenv('GITHUB_ORG')
    repo = args['repo_slug']
    file = args['file']
    filename = file['filename']
    b64 = file['b64']
    raw = base64.b64decode(b64)
    path = f'docs/assets/images/{filename}'
    put_file(owner, repo, path, raw, f'feat: upload image {filename}')
    return {"ok": True, "tool": "upload_image", "result": {"filename": filename}}


# TOOL: edit_homepage_copy

def tool_edit_homepage_copy(args: dict):
    owner = os.getenv('GITHUB_ORG')
    repo = args['repo_slug']
    instructions = args['instructions']
    # read index.html via contents api
    import base64
    from .github_tools import _get_file
    obj = _get_file(owner, repo, 'docs/index.html')
    if not obj:
        raise Exception('index.html not found')
    raw = base64.b64decode(obj['content']).decode()
    start = '<!--COPY_START-->'
    end = '<!--COPY_END-->''
    if start not in raw or end not in raw:
        raise Exception('Copy markers not found in index.html')
    prefix, rest = raw.split(start, 1)
    _, suffix = rest.split(end, 1)
    new_body = f"{prefix}{start}\n{instructions}\n{end}{suffix}"
    put_file(owner, repo, 'docs/index.html', new_body.encode(), 'feat: edit homepage copy')
    return {"ok": True, "tool": "edit_homepage_copy", "result": {"updated": True}}


# Worker entrypoint

def worker_execute(action: str, args: dict):
    # action -> tool wrapper mapping
    mapping = {
        'scaffold_site': tool_scaffold_site,
        'add_announcement': tool_add_announcement,
        'update_config': tool_update_config,
        'set_jumuah': tool_set_jumuah,
        'set_eid': tool_set_eid,
        'upload_image': tool_upload_image,
        'edit_homepage_copy': tool_edit_homepage_copy
    }
    if action not in mapping:
        return {"ok": False, "error": f'Unknown action {action}'}

    # call exactly one tool
    tool_fn = mapping[action]
    result = tool_fn(args)
    return result
