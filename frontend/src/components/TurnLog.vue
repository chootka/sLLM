<template>
  <div class="turnlog" :class="{ embedded }">
    <header v-if="!embedded" class="turnlog-head">
      <h1>Model log</h1>
      <div class="turnlog-meta">
        <span :class="loopRunning ? 'run on' : 'run off'">
          {{ loopRunning ? 'loop running' : 'loop stopped' }}
        </span>
        <span class="count">{{ turns.length }} turns</span>
        <label class="follow">
          <input type="checkbox" v-model="follow" /> follow
        </label>
        <a href="/">← dashboard</a>
      </div>
    </header>

    <p v-if="error" class="turnlog-error">{{ error }}</p>
    <p v-if="!turns.length && !error" class="turnlog-empty">
      No turns recorded yet. The loop writes one record per turn, including
      turns where it chose to do nothing.
    </p>

    <div class="turnlog-scroll" ref="scroller">
      <article v-for="t in turns" :key="t.datetime + '-' + t.turn" class="turn">
        <div class="turn-head">
          <time>{{ stamp(t.datetime) }}</time>
          <span class="turn-n">turn {{ t.turn }}</span>
          <span v-if="t.source && t.source !== 'live'" class="tag replay">
            {{ t.source }}
          </span>
          <span v-if="t.action" class="tag zone">
            zone {{ t.action.zone }} @ {{ t.action.intensity }}
            for {{ t.action.duration_s }}s
          </span>
          <span v-else class="tag none">no action</span>
          <!-- Only ever present for an authenticated admin. -->
          <span v-if="t.sham === true" class="tag sham">SHAM</span>
          <span v-else-if="t.sham === false" class="tag applied">applied</span>
        </div>

        <p class="turn-note">{{ t.note || '(no note)' }}</p>

        <p v-if="t.action_refused" class="turn-refused">
          action refused: {{ t.action_refused }}
        </p>

        <div v-if="t.state" class="turn-state">
          <span v-for="(v, ch) in t.state" :key="ch">
            {{ ch }}: period {{ fmt(v.period_s) }}s,
            amp {{ fmt(v.amplitude_mv) }}mV,
            drift {{ fmt(v.drift_mv_per_min) }}mV/min
          </span>
        </div>
      </article>
    </div>
  </div>
</template>

<script>
export default {
  name: 'TurnLog',
  props: {
    apiUrl: { type: String, required: true },
    // Hosted inside a dashboard panel rather than standing as the /logs page:
    // the panel supplies the heading and the link, so the component's own
    // header, turn count and follow toggle would be duplicate furniture.
    // Following is always on when embedded -- there is no room for a toggle,
    // and a panel that does not track the newest turn is just a stale box.
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      turns: [],
      loopRunning: null,
      error: '',
      follow: true,
      timer: null,
    }
  },
  mounted() {
    this.load()
    // Poll rather than use the socket: turns arrive every ten minutes, so a
    // websocket buys nothing here and this keeps working if the socket drops.
    this.timer = setInterval(this.load, 15000)
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
  },
  methods: {
    async load() {
      try {
        // `after` fetches only what is new once the first page is loaded.
        const last = this.turns.length
          ? `&after=${encodeURIComponent(this.turns[this.turns.length - 1].datetime)}`
          : ''
        const response = await fetch(`${this.apiUrl}/api/turns?limit=300${last}`)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = await response.json()
        this.loopRunning = data.loop_running
        if (data.turns.length) {
          this.turns = this.turns.concat(data.turns).slice(-500)
          if (this.follow) this.$nextTick(this.toBottom)
        }
        this.error = ''
      } catch (e) {
        this.error = `Could not load turns: ${e.message}`
      }
    },
    toBottom() {
      const el = this.$refs.scroller
      if (el) el.scrollTop = el.scrollHeight
    },
    stamp(iso) {
      // DD.MM.YYYY HH:MM:SS, from the ISO string's own offset -- these are
      // already local to the rig, so re-parsing through Date would shift them
      // to the reader's timezone.
      if (!iso) return ''
      const [date, rest = ''] = iso.split('T')
      const [year, month, day] = date.split('-')
      if (!year || !month || !day) return iso
      return `${day}.${month}.${year} ${rest.slice(0, 8)}`.trim()
    },
    fmt(v) {
      return v === null || v === undefined ? '—' : v
    },
  },
}
</script>

<style scoped>
/* Monochrome, matching the dashboard: no hue, so the tags are told apart by
   border weight and by their words, which is what they should have rested on
   in the first place. */
.turnlog {
  max-width: 60rem; margin: 0 auto; padding: 1.5rem 1rem;
  color: var(--ink-dim);
  font-family: ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace;
}
/* In a panel the host supplies the frame, so the component adds no padding,
   no width cap and no border of its own. */
.turnlog.embedded { max-width: none; margin: 0; padding: 0; }
.turnlog.embedded .turnlog-scroll {
  height: auto; border: none; padding: 0.25rem 0 0; background: transparent;
}

.turnlog-head { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: 1rem; justify-content: space-between; margin-bottom: 1rem; }
.turnlog-head h1 { font-size: 0.8rem; margin: 0; color: var(--ink);
  letter-spacing: 0.16em; text-transform: uppercase; font-weight: 500; }
.turnlog-meta { display: flex; gap: 1rem; align-items: center;
  font-size: 0.72rem; color: var(--ink-faint); }
.turnlog-meta a { color: var(--ink-dim); text-decoration: none;
  border-bottom: 1px solid var(--rule); }
.turnlog-meta a:hover { color: var(--ink); }
.run.on { color: var(--ink); }
.run.off { color: var(--ink-faint); }
.follow { cursor: pointer; user-select: none; }

.turnlog-scroll {
  height: 75vh; overflow-y: auto; border: 1px solid var(--rule);
  padding: 0.5rem; background: var(--paper-panel);
}

.turn { border-bottom: 1px solid var(--rule);
  padding: 0.7rem 0.5rem; }
.turn:last-child { border-bottom: none; }
.turn-head { display: flex; flex-wrap: wrap; gap: 0.5rem;
  align-items: center; font-size: 0.7rem; margin-bottom: 0.35rem; }
.turn-head time { color: var(--ink-faint); }
.turn-n { color: var(--ink-dim); }

.tag { padding: 0.05rem 0.4rem; font-size: 0.68rem;
  letter-spacing: 0.04em; border: 1px solid var(--rule);
  color: var(--ink-dim); }
.tag.zone { color: var(--ink); border-color: var(--rule-strong); }
.tag.none { color: var(--ink-ghost); border-color: var(--rule); }
.tag.replay { color: var(--ink-faint); border-style: dashed; }
/* The two that matter most keep the strongest rule on the page: a sham turn
   that reads as an applied one is a data-integrity problem, not a styling one. */
.tag.sham { color: var(--ink); border-color: var(--ink); border-style: dashed; }
.tag.applied { color: var(--ink); border-color: var(--ink); }

.turn-note { margin: 0.2rem 0; line-height: 1.45; font-size: 0.82rem;
  color: var(--ink); white-space: pre-wrap; }
.turn-refused { color: var(--ink-dim); font-size: 0.78rem; margin: 0.3rem 0 0;
  border-left: 2px dashed var(--rule-strong); padding-left: 0.5rem; }
.turn-state { display: flex; flex-wrap: wrap; gap: 0.9rem;
  font-size: 0.68rem; color: var(--ink-faint); margin-top: 0.35rem; }
.turnlog-error { color: var(--ink); border-left: 2px solid var(--ink);
  padding-left: 0.5rem; }
.turnlog-empty { color: var(--ink-faint); }
</style>
