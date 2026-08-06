<template>
  <div class="turnlog">
    <header class="turnlog-head">
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

        <p v-if="t.resource" class="turn-resource">
          RESOURCE REQUESTED: {{ t.resource }}
        </p>
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
      if (!iso) return ''
      return iso.replace('T', ' ').slice(0, 19)
    },
    fmt(v) {
      return v === null || v === undefined ? '—' : v
    },
  },
}
</script>

<style scoped>
.turnlog {
  max-width: 60rem; margin: 0 auto; padding: 1.5rem 1rem;
  color: #ccc; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.turnlog-head { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: 1rem; justify-content: space-between; margin-bottom: 1rem; }
.turnlog-head h1 { font-size: 1.1rem; margin: 0; color: #eee; }
.turnlog-meta { display: flex; gap: 1rem; align-items: center;
  font-size: 0.8rem; color: #888; }
.turnlog-meta a { color: #7fb5d5; text-decoration: none; }
.run.on { color: #6ec46e; }
.run.off { color: #999; }
.follow { cursor: pointer; user-select: none; }

.turnlog-scroll {
  height: 75vh; overflow-y: auto; border: 1px solid #333;
  border-radius: 6px; padding: 0.5rem; background: #101010;
}

.turn { border-bottom: 1px solid #232323; padding: 0.7rem 0.5rem; }
.turn:last-child { border-bottom: none; }
.turn-head { display: flex; flex-wrap: wrap; gap: 0.5rem;
  align-items: center; font-size: 0.75rem; margin-bottom: 0.35rem; }
.turn-head time { color: #7a7a7a; }
.turn-n { color: #999; }

.tag { padding: 0.05rem 0.4rem; border-radius: 3px; font-size: 0.7rem;
  border: 1px solid #444; }
.tag.zone { color: #9ecbff; border-color: #2c4a63; }
.tag.none { color: #777; }
.tag.replay { color: #d9b26a; border-color: #5c4a24; }
.tag.sham { color: #e0a0a0; border-color: #5c2c2c; }
.tag.applied { color: #6ec46e; border-color: #2c5c2c; }

.turn-note { margin: 0.2rem 0; line-height: 1.45; font-size: 0.85rem;
  color: #ddd; white-space: pre-wrap; }
.turn-resource { color: #e0c07a; font-size: 0.8rem; margin: 0.3rem 0 0; }
.turn-refused { color: #e08080; font-size: 0.8rem; margin: 0.3rem 0 0; }
.turn-state { display: flex; flex-wrap: wrap; gap: 0.9rem;
  font-size: 0.7rem; color: #6e6e6e; margin-top: 0.35rem; }
.turnlog-error { color: #e08080; }
.turnlog-empty { color: #777; }
</style>
