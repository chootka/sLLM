<template>
  <section class="phaselock" v-if="visible">
    <header class="pl-head">
      <h2>Phase lock</h2>
      <select v-model.number="hours" @change="load">
        <option :value="6">6 h</option>
        <option :value="24">24 h</option>
        <option :value="72">3 d</option>
        <option :value="168">7 d</option>
      </select>
    </header>

    <p class="pl-note">
      Where in the organism's cycle the light actually arrived. Spread means the
      stimulus is landing anywhere, which is what a fixed clock produces.
      Clustered means it is arriving at a preferred phase.
    </p>

    <p v-if="error" class="pl-error">{{ error }}</p>

    <template v-else-if="data">
      <p v-if="data.verdict === 'insufficient'" class="pl-thin">
        {{ data.detail || 'not enough yet' }}
      </p>

      <template v-else>
        <div class="pl-bars">
          <div v-for="(count, i) in data.bins" :key="i" class="pl-bar-cell">
            <div class="pl-bar" :style="{ height: barHeight(count) }"></div>
            <span class="pl-tick" v-if="i % 3 === 0">
              {{ Math.round(data.bin_edges_deg[i]) }}&deg;
            </span>
          </div>
        </div>

        <dl class="pl-stats">
          <div><dt>onsets</dt><dd>{{ data.n_onsets }}</dd></div>
          <div><dt>period</dt><dd>{{ Math.round(data.period_s) }}s</dd></div>
          <div><dt>R</dt><dd>{{ data.R.toFixed(3) }}</dd></div>
          <div>
            <dt>null</dt>
            <dd>{{ data.null_mean.toFixed(3) }} &plusmn; {{ data.null_sd.toFixed(3) }}</dd>
          </div>
          <div><dt>p</dt><dd>{{ data.p.toFixed(3) }}</dd></div>
        </dl>

        <p class="pl-verdict" :class="data.verdict">
          {{ data.verdict === 'clustered'
             ? 'clustered — arriving at a preferred phase'
             : 'not distinguishable from arbitrary' }}
        </p>
      </template>
    </template>

    <p v-else class="pl-thin">loading…</p>
  </section>
</template>

<script>
export default {
  name: 'PhaseLock',
  props: { apiUrl: { type: String, default: '' } },
  data() {
    return { data: null, error: '', hours: 24, visible: false, timer: null }
  },
  mounted() {
    this.load()
    // Slow: the underlying quantity moves over hours, and the shuffled null is
    // the most expensive thing the Pi is asked to compute.
    this.timer = setInterval(this.load, 5 * 60 * 1000)
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
  },
  methods: {
    barHeight(count) {
      const peak = Math.max(...this.data.bins, 1)
      return `${Math.max(2, (count / peak) * 100)}%`
    },
    async load() {
      try {
        const r = await fetch(
          `${this.apiUrl}/api/phase-lock?hours=${this.hours}`,
          { credentials: 'include' })
        if (r.status === 403) {
          // Admin only, because light onsets are the record of which turns
          // were not shams. Hide rather than show a refusal.
          this.visible = false
          return
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        this.data = await r.json()
        this.error = ''
        this.visible = true
      } catch (e) {
        this.error = String(e.message || e)
        this.visible = true
      }
    },
  },
}
</script>

<style scoped>
.phaselock { margin: 1.5rem 0; }
.pl-head { display: flex; align-items: baseline; gap: .75rem; }
.pl-head h2 { margin: 0; font-size: 1rem; }
.pl-note { opacity: .7; font-size: .8rem; margin: .35rem 0 .75rem; max-width: 46em; }
.pl-error { color: #c33; font-size: .85rem; }
.pl-thin { opacity: .6; font-size: .85rem; }
.pl-bars {
  display: flex; align-items: flex-end; gap: 2px;
  height: 120px; padding-bottom: 1.1rem; position: relative;
}
.pl-bar-cell { flex: 1; height: 100%; display: flex; align-items: flex-end; position: relative; }
.pl-bar { width: 100%; background: currentColor; opacity: .75; }
.pl-tick {
  position: absolute; bottom: -1.1rem; left: 0;
  font-size: .65rem; opacity: .5; white-space: nowrap;
}
.pl-stats { display: flex; gap: 1.25rem; margin: .5rem 0 .25rem; font-size: .8rem; }
.pl-stats div { display: flex; gap: .35rem; }
.pl-stats dt { opacity: .6; }
.pl-stats dd { margin: 0; font-variant-numeric: tabular-nums; }
.pl-verdict { font-size: .85rem; margin: .25rem 0 0; }
.pl-verdict.clustered { font-weight: 600; }
.pl-verdict.arbitrary { opacity: .7; }
</style>
