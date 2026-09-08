<template>
  <div class="archive" :class="{ embedded }">
    <header v-if="!embedded" class="ar-head">
      <h1>Runs</h1>
      <a href="/">← dashboard</a>
    </header>

    <p v-if="!embedded" class="ar-note">
      Every recording run, newest first. A run is one dish under one
      configuration: the readings, the timelapse and the model's turns all
      carry its id, so what follows is the whole record of that dish.
    </p>

    <p v-if="error" class="ar-error">{{ error }}</p>

    <div class="ar-body">
      <select v-if="embedded" class="ar-picker" :value="selected"
              @change="select($event.target.value)">
        <option v-for="r in runs" :key="r.id" :value="r.id">
          {{ stamp(r.started_at_iso) }} · {{ r.mode }}{{ r.experiment ? ' · ' + r.experiment : '' }}
          · {{ duration(r.duration_s) }}{{ r.recording ? ' · recording' : '' }}
        </option>
      </select>

      <ul v-else class="ar-list">
        <li v-for="r in runs" :key="r.id">
          <button class="ar-item" :class="{ on: r.id === selected }"
                  @click="select(r.id)">
            <span class="ar-id">{{ stamp(r.started_at_iso) }}</span>
            <span class="ar-tags">
              <span class="tag" :class="r.mode">{{ r.mode }}</span>
              <span v-if="r.recording" class="tag rec">recording</span>
              <span v-if="r.experiment" class="tag">{{ r.experiment }}</span>
            </span>
            <span class="ar-dur">{{ duration(r.duration_s) }}</span>
          </button>
        </li>
      </ul>

      <section v-if="detail" class="ar-detail">
        <h2>{{ detail.run.id }}</h2>

        <dl class="ar-facts">
          <dt>started</dt><dd>{{ stamp(detail.run.started_at_iso) }}</dd>
          <dt>ended</dt>
          <dd>{{ detail.run.ended_at_iso ? stamp(detail.run.ended_at_iso) : 'still recording' }}</dd>
          <dt>duration</dt><dd>{{ duration(detail.run.duration_s) }}</dd>
          <dt>mode</dt><dd>{{ detail.run.mode }}</dd>
          <dt>experiment</dt><dd>{{ detail.run.experiment || '—' }}</dd>
          <dt>dish</dt><dd>{{ detail.run.electrodes || '—' }}</dd>
          <dt>samples</dt><dd>{{ detail.samples === null ? '—' : detail.samples }}</dd>
          <dt>turns</dt><dd>{{ detail.turns }}</dd>
        </dl>

        <p v-if="detail.run.note" class="ar-runnote">{{ detail.run.note }}</p>

        <h3>Timelapse</h3>
        <!-- Segments are cut on frame count, not on runs, so a segment can
             hold several runs. seek_s is where this run starts inside it. -->
        <p v-if="!detail.segments.length" class="ar-thin">
          No encoded video covers this run yet. Frames are archived hourly.
        </p>
        <div v-for="seg in detail.segments" :key="seg.file" class="ar-seg">
          <video controls preload="metadata" :src="apiUrl + seg.url"
                 @loadedmetadata="seek($event, seg)"></video>
          <p class="ar-thin">
            {{ seg.file }} — {{ seg.frames_in_run || 0 }} of {{ seg.frames }}
            frames are from this run<span v-if="seg.seek_s">, starting
            {{ seg.seek_s }}s in</span><span v-if="seg.thinned">; thinned
            archive</span>
          </p>
        </div>

        <h3>Model log</h3>
        <TurnLog :api-url="apiUrl" :run="detail.run.id" embedded />
      </section>

      <p v-else-if="!error" class="ar-thin">Select a run.</p>
    </div>
  </div>
</template>

<script>
import TurnLog from './TurnLog.vue'

export default {
  name: 'RunArchive',
  components: { TurnLog },
  props: {
    apiUrl: { type: String, default: '' },
    // In the dashboard grid: no page heading, a dropdown instead of a
    // two-column list, and the URL hash left alone -- the dashboard owns it.
    embedded: { type: Boolean, default: false },
  },
  data() {
    return { runs: [], selected: '', detail: null, error: '' }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      try {
        const r = await fetch(`${this.apiUrl}/api/runs?limit=200`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const d = await r.json()
        this.runs = d.runs
        // Deep link first, then whatever is recording, then the newest.
        const wanted = this.embedded ? '' : window.location.hash.replace(/^#/, '')
        const exists = this.runs.some((run) => run.id === wanted)
        const first = exists ? wanted : (d.current || (this.runs[0] || {}).id)
        if (first) this.select(first)
      } catch (e) {
        this.error = `Could not load runs: ${e.message}`
      }
    },
    async select(id) {
      this.selected = id
      this.detail = null
      if (!this.embedded) window.location.hash = id
      try {
        const r = await fetch(`${this.apiUrl}/api/runs/${encodeURIComponent(id)}`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        this.detail = await r.json()
        this.error = ''
      } catch (e) {
        this.error = `Could not load ${id}: ${e.message}`
      }
    },
    // Start the player where this run begins rather than at the segment's
    // first frame, which can be days earlier.
    seek(event, seg) {
      if (seg.seek_s) event.target.currentTime = seg.seek_s
    },
    stamp(iso) {
      if (!iso) return '—'
      const [date, rest = ''] = iso.split('T')
      const [year, month, day] = date.split('-')
      if (!year) return iso
      return `${day}.${month}.${year} ${rest.slice(0, 5)}`
    },
    duration(s) {
      if (s === null || s === undefined) return '—'
      if (s < 3600) return `${Math.round(s / 60)} min`
      const hours = s / 3600
      return hours < 48 ? `${hours.toFixed(1)} h` : `${(hours / 24).toFixed(1)} d`
    },
  },
}
</script>

<style scoped>
.archive { max-width: 64rem; margin: 0 auto; padding: 1.5rem 1rem; }
.ar-head { display: flex; align-items: baseline; gap: 1rem; }
.ar-head h1 { margin: 0; font-size: 1.2rem; }
.ar-note { opacity: .7; font-size: .85rem; max-width: 46em; margin: .5rem 0 1.2rem; }
.ar-error { color: #c33; font-size: .85rem; }
.ar-thin { opacity: .6; font-size: .85rem; }

.ar-body { display: grid; grid-template-columns: minmax(15rem, 22rem) 1fr; gap: 1.5rem; }
@media (max-width: 44rem) { .ar-body { grid-template-columns: 1fr; } }

.archive.embedded { max-width: none; margin: 0; padding: 0; }
.archive.embedded .ar-body { display: block; }
.ar-picker { width: 100%; font: inherit; margin-bottom: .8rem; }
.archive.embedded .ar-detail h2 { display: none; }
.archive.embedded .ar-seg video { max-height: 40vh; }

.ar-list { list-style: none; margin: 0; padding: 0; max-height: 80vh; overflow-y: auto; }
.ar-item {
  display: grid; grid-template-columns: 1fr auto; gap: .2rem .5rem;
  width: 100%; text-align: left; background: none; border: 0;
  border-bottom: 1px solid currentColor; border-color: rgba(128,128,128,.25);
  padding: .5rem .3rem; font: inherit; color: inherit; cursor: pointer;
}
.ar-item:hover { background: rgba(128, 128, 128, .08); }
.ar-item.on { background: rgba(128, 128, 128, .16); }
.ar-id { font-variant-numeric: tabular-nums; }
.ar-dur { opacity: .6; font-size: .85rem; font-variant-numeric: tabular-nums; }
.ar-tags { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: .3rem; }

.tag {
  font-size: .7rem; text-transform: uppercase; letter-spacing: .04em;
  border: 1px solid currentColor; border-radius: 2px; padding: 0 .3rem; opacity: .7;
}
.tag.live { opacity: 1; font-weight: 600; }
.tag.rec { opacity: 1; }

.ar-detail h2 { font-size: 1rem; margin: 0 0 .8rem; font-variant-numeric: tabular-nums; }
.ar-detail h3 { font-size: .9rem; margin: 1.4rem 0 .5rem; }
.ar-facts { display: grid; grid-template-columns: auto 1fr; gap: .2rem .8rem; margin: 0; font-size: .85rem; }
.ar-facts dt { opacity: .6; }
.ar-facts dd { margin: 0; }
.ar-runnote { font-size: .85rem; margin: .8rem 0 0; }
.ar-seg { margin: 0 0 1.2rem; }
.ar-seg video { width: 100%; max-height: 60vh; background: #000; }
</style>
