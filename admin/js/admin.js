// admin.js — handles register/login + dashboard actions

const tokenKey = 'ms_token'

async function api(path, method='GET', body=null) {
  const headers = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem(tokenKey)
  if (token) headers['Authorization'] = 'Bearer ' + token
  const resp = await fetch(BACKEND_BASE_URL + path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  return await resp.json()
}

// Login / register
if (document.getElementById('btn-login')) {
  document.getElementById('btn-register').onclick = async () => {
    const email = document.getElementById('email').value
    const password = document.getElementById('password').value
    const r = await api('/auth/register', 'POST', { email, password })
    if (r.token) { localStorage.setItem(tokenKey, r.token); alert('Registered'); location.href = 'dashboard.html' }
    else alert(JSON.stringify(r))
  }
  document.getElementById('btn-login').onclick = async () => {
    const email = document.getElementById('email').value
    const password = document.getElementById('password').value
    const r = await api('/auth/login', 'POST', { email, password })
    if (r.token) { localStorage.setItem(tokenKey, r.token); alert('Logged in'); location.href = 'dashboard.html' }
    else alert(JSON.stringify(r))
  }
}

// Dashboard behavior
if (document.getElementById('btn-create')) {
  // Create website
  document.getElementById('btn-create').onclick = async () => {
    const name = document.getElementById('mosque-name').value
    const location = document.getElementById('mosque-location').value
    const files = document.getElementById('mosque-images').files
    const images = []
    for (let f of files) {
      const b64 = await fileToBase64(f)
      images.push({ filename: f.name, b64: b64.split(',')[1] })
    }
    const instruction = `Create a new mosque website with name: ${name} and location: ${location}`
    const body = { repo_slug: null, instruction, context: { name, location, images } }
    const r = await api('/manager/act', 'POST', body)
    document.getElementById('ai-result').textContent = JSON.stringify(r, null, 2)
  }

  // AI Manager send
  document.getElementById('btn-send').onclick = async () => {
    const instruction = document.getElementById('ai-instruction').value
    const repo_slug = document.getElementById('ai-repo').value || null
    const r = await api('/manager/act', 'POST', { repo_slug, instruction, context: {} })
    document.getElementById('ai-result').textContent = JSON.stringify(r, null, 2)
  }

  document.getElementById('btn-get-commits').onclick = async () => {
    const repo = document.getElementById('commits-repo').value
    const r = await api(`/repos/${repo}/commits`)
    const list = document.getElementById('commits-list')
    list.innerHTML = ''
    if (Array.isArray(r)) {
      for (let c of r) {
        const li = document.createElement('li')
        li.innerHTML = `<b>${c.sha.slice(0,7)}</b> - ${c.message} - <a href='${c.url}' target='_blank'>view</a>`
        list.appendChild(li)
      }
    } else {
      list.innerHTML = '<li>' + JSON.stringify(r) + '</li>'
    }
  }
}

function fileToBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = () => res(r.result)
    r.onerror = rej
    r.readAsDataURL(file)
  })
}
