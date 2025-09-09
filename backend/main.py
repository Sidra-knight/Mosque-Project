# main.py — FastAPI app wiring everything together
import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

from .db import _conn
from .auth import hash_password, verify_password, create_access_token, decode_token
from .manager_worker import manager_plan, _merge_args, worker_execute
from .github_tools import get_commits

ADMIN_ORIGIN = os.getenv('ADMIN_ORIGIN', 'http://localhost:5500')

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=[ADMIN_ORIGIN], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


class AuthIn(BaseModel):
    email: str
    password: str


@app.post('/auth/register')
def register(body: AuthIn):
    cur = _conn.cursor()
    cur.execute('SELECT id FROM users WHERE email=?', (body.email.lower(),))
    if cur.fetchone():
        raise HTTPException(400, 'Email already registered')
    ph = hash_password(body.password)
    cur.execute('INSERT INTO users (email, password_hash) VALUES (?,?)', (body.email.lower(), ph))
    _conn.commit()
    token = create_access_token(body.email.lower())
    return {"token": token}


@app.post('/auth/login')
def login(body: AuthIn):
    cur = _conn.cursor()
    cur.execute('SELECT password_hash FROM users WHERE email=?', (body.email.lower(),))
    row = cur.fetchone()
    if not row:
        raise HTTPException(401, 'Invalid credentials')
    if not verify_password(body.password, row['password_hash']):
        raise HTTPException(401, 'Invalid credentials')
    token = create_access_token(body.email.lower())
    return {"token": token}


# dependency

def get_current_user(request: Request):
    auth = request.headers.get('authorization')
    if not auth:
        raise HTTPException(401, 'Missing auth')
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(401, 'Bad auth header')
    payload = decode_token(parts[1])
    if not payload or 'sub' not in payload:
        raise HTTPException(401, 'Invalid token')
    return payload['sub']


class ManagerActIn(BaseModel):
    repo_slug: str = None
    instruction: str
    context: dict = {}


@app.post('/manager/act')
def manager_act(body: ManagerActIn, user=Depends(get_current_user)):
    try:
        plan = manager_plan(body.instruction, body.context)
    except Exception as e:
        return {"status": "error", "message": f'Manager error: {e}'}

    action = plan['action']
    manager_args = plan['args']
    final_args = _merge_args(manager_args, body.context)

    # ensure repo_slug presence when required
    if action != 'scaffold_site' and not final_args.get('repo_slug'):
        # try to fall back to provided body.repo_slug
        if body.repo_slug:
            final_args['repo_slug'] = body.repo_slug
        else:
            return {"status": "error", "message": 'repo_slug required for this action', "action": plan}

    # call worker
    try:
        worker_result = worker_execute(action, final_args)
    except Exception as e:
        return {"status": "error", "message": f'Worker exception: {e}', "action": plan}

    out = {"status": "ok", "message": f'Action {action} executed', "action": plan, "worker_result": worker_result}
    if action == 'scaffold_site' and worker_result.get('result'):
        repo = worker_result['result'].get('created_repo')
        out['repo_slug'] = repo.split('/')[-1]
    return out


@app.get('/repos/{repo_slug}/commits')
def repo_commits(repo_slug: str, user=Depends(get_current_user)):
    owner = os.getenv('GITHUB_ORG')
    try:
        commits = get_commits(owner, repo_slug)
        simplified = [{"sha": c['sha'], "message": c['commit']['message'], "url": c['html_url']} for c in commits]
        return simplified
    except Exception as e:
        raise HTTPException(400, str(e))


# if run as module
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
