<template>
  <div class="admin">
    <button class="admin-toggle" @click="toggle" :title="open ? 'close admin' : 'admin'">
      {{ open ? '×' : '⚙' }}
    </button>

    <div v-if="open" class="admin-panel">
      <h3>Admin</h3>

      <p v-if="error" class="admin-error">{{ error }}</p>
      <p v-if="notice" class="admin-notice">{{ notice }}</p>

      <!-- Enrolment: only offered when the page was opened with a token from
           scripts/enrol_passkey.py, which requires a shell on the Pi. -->
      <div v-if="enrolToken">
        <p>Register this device as an admin passkey.</p>
        <button class="admin-action" :disabled="busy" @click="enrol">
          Register this device
        </button>
      </div>

      <div v-else-if="!authenticated">
        <p v-if="!enrolled">
          No passkey is enrolled. Run
          <code>scripts/enrol_passkey.py</code> on the Pi and open the link it
          prints.
        </p>
        <button v-else class="admin-action" :disabled="busy" @click="login">
          Sign in with passkey
        </button>
      </div>

      <div v-else>
        <p class="admin-status">
          Model loop:
          <strong :class="loopActive ? 'on' : 'off'">
            {{ loopActive ? 'RUNNING' : 'stopped' }}
          </strong>
        </p>
        <button class="admin-action" :disabled="busy || loopActive"
                @click="setLoop('start')">Start loop</button>
        <button class="admin-action" :disabled="busy || !loopActive"
                @click="setLoop('stop')">Stop loop</button>

        <hr class="admin-rule" />

        <p class="admin-status">
          Demo mode:
          <strong :class="demoActive ? 'demo' : 'off'">
            {{ demoActive ? 'RUNNING' : 'stopped' }}
          </strong>
        </p>
        <button class="admin-action"
                :disabled="busy || demoActive || occupied"
                @click="setUnit('demo', 'start')">Start demo</button>
        <button class="admin-action" :disabled="busy || !demoActive"
                @click="setUnit('demo', 'stop')">Stop demo</button>
        <p class="admin-hint">
          Demo invents data and drives the real panel, fast, so the hardware can
          be watched. Starting it stops the model loop, and vice versa — they
          share the panel.
        </p>

        <hr class="admin-rule" />

        <p class="admin-status">
          Recording:
          <strong :class="mode === 'experiment' ? 'on' : 'demo'">{{ mode }}</strong>
        </p>
        <button v-for="m in modes" :key="m" class="admin-action"
                :disabled="busy || mode === m" @click="setMode(m)">
          {{ m }}
        </button>
        <p class="admin-hint">
          Nothing stops recording. Anything but <em>experiment</em> is tagged
          and written to its own directory, so it is excluded by a filter rather
          than by a hole in the series. Starting a demo switches this
          automatically; coming back is deliberate, because only you know when
          the organism is actually back in.
        </p>

        <hr class="admin-rule" />

        <p class="admin-status">
          Chamber:
          <strong :class="occupied ? 'occupied' : 'off'">
            {{ occupied ? 'OCCUPIED' : 'empty' }}
          </strong>
        </p>
        <button class="admin-action" :disabled="busy"
                @click="setChamber(!occupied)">
          {{ occupied ? 'Mark chamber empty' : 'Mark chamber occupied' }}
        </button>
        <p class="admin-hint">
          Nothing can detect this — you assert it. While occupied, demo mode
          refuses to run so invented stimulus never reaches a living organism.
        </p>

        <hr class="admin-rule" />

        <button class="admin-action subtle" @click="logout">Sign out</button>
        <p class="admin-hint">
          The session is held in memory only, so reloading this page signs you
          out.
        </p>
      </div>
    </div>
  </div>
</template>

<script>
// WebAuthn speaks ArrayBuffers; the server speaks base64url. These two convert
// between them. Note base64url, not plain base64: '-' and '_' rather than '+'
// and '/', and no padding.
function b64urlToBuffer(value) {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/')
  const binary = atob(padded + '='.repeat((4 - (padded.length % 4)) % 4))
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

function bufferToB64url(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

export default {
  name: 'AdminPanel',
  props: {
    apiUrl: { type: String, required: true },
  },
  data() {
    return {
      open: false,
      busy: false,
      error: '',
      notice: '',
      enrolled: false,
      authenticated: false,
      loopActive: false,
      demoActive: false,
      occupied: false,
      mode: '',
      modes: [],
      // The session token lives here and nowhere else. Not a cookie (no CSRF
      // surface) and not localStorage (an XSS would have to run while the
      // session is live rather than harvest it later).
      token: '',
      enrolToken: new URLSearchParams(window.location.search).get('enrol') || '',
    }
  },
  mounted() {
    // Only reveal the panel automatically when arriving from an enrolment link.
    if (this.enrolToken) this.open = true
    this.refreshState()
  },
  methods: {
    toggle() {
      this.open = !this.open
      if (this.open) this.refreshState()
    },

    async refreshState() {
      try {
        const response = await fetch(`${this.apiUrl}/api/admin/state`)
        const data = await response.json()
        this.enrolled = data.enrolled
      } catch (e) {
        this.error = 'Could not reach the admin API.'
      }
    },

    async post(path, body, authed = false) {
      const headers = { 'Content-Type': 'application/json' }
      if (authed) headers.Authorization = `Bearer ${this.token}`
      const response = await fetch(`${this.apiUrl}/api/admin/${path}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body || {}),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`)
      return data
    },

    async enrol() {
      this.busy = true
      this.error = ''
      this.notice = ''
      try {
        // `label` comes from the --label passed to enrol_passkey.py. It has to
        // be handed back at verify time or every credential is stored as the
        // default "passkey" and --revoke cannot tell two devices apart.
        const { challenge_id, options, label } = await this.post('enrol/options', {
          enrol_token: this.enrolToken,
        })

        options.challenge = b64urlToBuffer(options.challenge)
        options.user.id = b64urlToBuffer(options.user.id)
        for (const cred of options.excludeCredentials || []) {
          cred.id = b64urlToBuffer(cred.id)
        }

        const credential = await navigator.credentials.create({ publicKey: options })

        await this.post('enrol/verify', {
          challenge_id,
          label,
          credential: {
            id: credential.id,
            rawId: bufferToB64url(credential.rawId),
            type: credential.type,
            response: {
              clientDataJSON: bufferToB64url(credential.response.clientDataJSON),
              attestationObject: bufferToB64url(credential.response.attestationObject),
            },
          },
        })

        this.notice = 'Passkey registered. You can sign in with it now.'
        this.enrolToken = ''
        this.enrolled = true
        // Strip the spent token from the address bar so it is not re-shared.
        window.history.replaceState({}, '', window.location.pathname)
      } catch (e) {
        this.error = e.message || 'Registration failed.'
      } finally {
        this.busy = false
      }
    },

    async login() {
      this.busy = true
      this.error = ''
      this.notice = ''
      try {
        const { challenge_id, options } = await this.post('login/options')

        options.challenge = b64urlToBuffer(options.challenge)
        for (const cred of options.allowCredentials || []) {
          cred.id = b64urlToBuffer(cred.id)
        }

        const assertion = await navigator.credentials.get({ publicKey: options })

        const data = await this.post('login/verify', {
          challenge_id,
          credential: {
            id: assertion.id,
            rawId: bufferToB64url(assertion.rawId),
            type: assertion.type,
            response: {
              clientDataJSON: bufferToB64url(assertion.response.clientDataJSON),
              authenticatorData: bufferToB64url(assertion.response.authenticatorData),
              signature: bufferToB64url(assertion.response.signature),
              userHandle: assertion.response.userHandle
                ? bufferToB64url(assertion.response.userHandle)
                : null,
            },
          },
        })

        this.token = data.token
        this.authenticated = true
        await this.refreshLoop()
      } catch (e) {
        this.error = e.message || 'Authentication failed.'
      } finally {
        this.busy = false
      }
    },

    async refreshLoop() {
      try {
        const response = await fetch(`${this.apiUrl}/api/admin/loop`, {
          headers: { Authorization: `Bearer ${this.token}` },
        })
        if (response.status === 401) {
          this.authenticated = false
          this.token = ''
          this.error = 'Session expired. Sign in again.'
          return
        }
        const data = await response.json()
        this.loopActive = data.units ? data.units.loop.active : data.active
        this.demoActive = data.units ? data.units.demo.active : false
        await this.refreshChamber()
        await this.refreshRun()
      } catch (e) {
        this.error = 'Could not read loop state.'
      }
    },

    async refreshChamber() {
      try {
        const response = await fetch(`${this.apiUrl}/api/admin/chamber`, {
          headers: { Authorization: `Bearer ${this.token}` },
        })
        if (!response.ok) return
        const data = await response.json()
        this.occupied = data.occupied
      } catch (e) {
        // Non-fatal: the loop controls still work without this.
      }
    },

    async refreshRun() {
      try {
        const response = await fetch(`${this.apiUrl}/api/admin/run`, {
          headers: { Authorization: `Bearer ${this.token}` },
        })
        if (!response.ok) return
        const data = await response.json()
        this.mode = data.run.mode
        this.modes = data.modes
      } catch (e) {
        // Non-fatal.
      }
    },

    async setMode(mode) {
      this.busy = true
      this.error = ''
      this.notice = ''
      try {
        const data = await this.post('run', { mode }, true)
        this.mode = data.run.mode
        this.notice = `Recording as ${data.run.mode}.`
      } catch (e) {
        this.error = e.message || 'Could not switch mode.'
      } finally {
        this.busy = false
      }
    },

    async setChamber(occupied) {
      this.busy = true
      this.error = ''
      this.notice = ''
      try {
        const data = await this.post('chamber', { occupied }, true)
        this.occupied = data.occupied
        this.notice = `Chamber marked ${data.occupied ? 'occupied' : 'empty'}.`
      } catch (e) {
        this.error = e.message || 'Could not set the chamber flag.'
      } finally {
        this.busy = false
      }
    },

    async setUnit(unit, action) {
      this.busy = true
      this.error = ''
      this.notice = ''
      try {
        const data = await this.post('loop', { action, unit }, true)
        if (data.units) {
          this.loopActive = data.units.loop.active
          this.demoActive = data.units.demo.active
        }
        this.notice = `${unit} ${data.state}.`
      } catch (e) {
        this.error = e.message || `Could not ${action} ${unit}.`
      } finally {
        this.busy = false
      }
    },

    async setLoop(action) {
      this.busy = true
      this.error = ''
      this.notice = ''
      try {
        const data = await this.post('loop', { action, unit: 'loop' }, true)
        if (data.units) {
          this.loopActive = data.units.loop.active
          this.demoActive = data.units.demo.active
        } else {
          this.loopActive = data.active
        }
        this.notice = `Loop ${data.state}.`
      } catch (e) {
        this.error = e.message || `Could not ${action} the loop.`
      } finally {
        this.busy = false
      }
    },

    async logout() {
      try {
        await this.post('logout', {}, true)
      } catch (e) {
        // Signing out locally matters more than the server acknowledging it.
      }
      this.token = ''
      this.authenticated = false
      this.notice = 'Signed out.'
    },
  },
}
</script>

<style scoped>
.admin { position: fixed; right: 1rem; bottom: 1rem; z-index: 900; }

.admin-toggle {
  width: 2.2rem; height: 2.2rem; border-radius: 50%;
  border: 1px solid #444; background: #1b1b1b; color: #888;
  cursor: pointer; font-size: 1rem; line-height: 1;
}
.admin-toggle:hover { color: #ddd; border-color: #666; }

.admin-panel {
  position: absolute; right: 0; bottom: 2.8rem; width: 19rem;
  background: #131313; border: 1px solid #444; border-radius: 6px;
  padding: 0.9rem 1rem; color: #ccc; font-size: 0.85rem;
  box-shadow: 0 6px 24px rgba(0,0,0,0.5);
}
.admin-panel h3 { margin: 0 0 0.6rem; font-size: 0.9rem; color: #eee; }
.admin-panel p { margin: 0.4rem 0; line-height: 1.4; }
.admin-panel code { background: #222; padding: 0 0.25rem; border-radius: 3px; }

.admin-action {
  display: block; width: 100%; margin: 0.4rem 0; padding: 0.45rem;
  background: #222; border: 1px solid #555; border-radius: 4px;
  color: #ddd; cursor: pointer;
}
.admin-action:hover:not(:disabled) { background: #2c2c2c; border-color: #777; }
.admin-action:disabled { opacity: 0.4; cursor: not-allowed; }
.admin-action.subtle { border-color: #333; color: #888; }

.admin-status .on { color: #6ec46e; }
.admin-status .demo { color: #d9b26a; }
.admin-status .occupied { color: #e0a0a0; }
.admin-rule { border: none; border-top: 1px solid #2a2a2a; margin: 0.8rem 0 0.5rem; }
.admin-status .off { color: #999; }
.admin-error { color: #e08080; }
.admin-notice { color: #7fb5d5; }
.admin-hint { color: #666; font-size: 0.75rem; }
</style>
