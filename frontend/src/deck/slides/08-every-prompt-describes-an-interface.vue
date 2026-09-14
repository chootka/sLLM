<template>
<div class="content">
<h2>Every prompt describes an interface</h2>

<div class="prompts">
  <button
    v-for="(p, i) in prompts"
    :key="p.name"
    type="button"
    :aria-pressed="i === current"
    @click="current = i"
  >
    <span class="label">{{ p.name }}</span>
    <svg class="ico" aria-hidden="true"><use :href="'#ico-' + p.icon" /></svg>
  </button>
</div>

<div class="exchange">
  <div>
    <p class="label">Slime &rarr; model</p>
    <p>{{ prompts[current].receives }}</p>
  </div>
  <div class="arrow" aria-hidden="true"></div>
  <div>
    <p class="label">Model &rarr; slime</p>
    <p>{{ prompts[current].acts }}</p>
  </div>
</div>

<p class="note">The six prompt variants differ only in what the model is told it is
coupled to.</p>
</div>
<svg class="sprite" aria-hidden="true" focusable="false">
  <!-- coupled to something it is not shown -->
  <symbol id="ico-blind" viewBox="0 0 24 24">
    <path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z"/>
    <circle cx="12" cy="12" r="2.4"/><path d="M3.5 20.5 20.5 3.5"/>
  </symbol>
  <!-- the same interface, named -->
  <symbol id="ico-informed" viewBox="0 0 24 24">
    <path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12z"/>
    <circle cx="12" cy="12" r="2.4"/>
  </symbol>
  <!-- its activity eats the model's memory -->
  <symbol id="ico-adversarial" viewBox="0 0 24 24">
    <rect x="2.5" y="7.5" width="19" height="9" rx="1"/>
    <path d="M5.5 10.5h6v3h-6z" fill="currentColor" stroke="none"/>
    <path d="M17 3.5v3M15.5 5l1.5 1.5L18.5 5"/>
  </symbol>
  <!-- the period sets the budget -->
  <symbol id="ico-metered" viewBox="0 0 24 24">
    <path d="M3.5 17.5a9 9 0 0 1 17 0"/><path d="M12 17.5 16.5 10"/>
    <circle cx="12" cy="17.5" r="1.2" fill="currentColor" stroke="none"/>
  </symbol>
  <!-- a trail that fades, in place of memory -->
  <symbol id="ico-mimic" viewBox="0 0 24 24">
    <circle cx="19.5" cy="12" r="2.6" fill="currentColor" stroke="none"/>
    <circle cx="13.5" cy="12" r="2.1" fill="currentColor" stroke="none" opacity=".6"/>
    <circle cx="8.2" cy="12" r="1.7" fill="currentColor" stroke="none" opacity=".35"/>
    <circle cx="3.6" cy="12" r="1.3" fill="currentColor" stroke="none" opacity=".16"/>
  </symbol>
  <!-- nothing crosses -->
  <symbol id="ico-null" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="8.5"/><path d="M6 18 18 6"/>
  </symbol>
</svg>
<figure class="media"><img src="/deck-media/model-logs.jpg" alt="The model log: each turn's state, reply and applied action"></figure>
</template>

<script>
// Both directions are taken from llm/filters/prompts.md, one entry per variant.
export default {
  name: '08_every_prompt_describes_an_interface',
  meta: {
    classes: 'split content-wide overlap',
    section: 'The question',
    reg: 0.55, fx: 50, fy: 52
  },
  data() {
    return {
      current: 0,
      prompts: [
        {
          name: 'NULL',
          icon: 'null',
          receives: 'The same readings as BLIND, with no task. It is asked to describe what it sees and not to guess at causes.',
          acts: 'Nothing. No light. Any claim of influence in its notes comes from the prompt format, not the dish.'
        },
        {
          name: 'BLIND',
          icon: 'blind',
          receives: 'Three electrode readings over the last thirty minutes. It is not told what they come from.',
          acts: 'Light one of nine zones, for a duration it picks. It is not told whether the light did anything.'
        },
        {
          name: 'INFORMED',
          icon: 'informed',
          receives: 'The same readings, with the organism named: Physarum, about a millivolt, blue light aversive, plus the zone map. The period is withheld.',
          acts: 'Light one of nine zones. Any difference from BLIND comes from what it already knew about slime moulds.'
        },
        {
          name: 'ADVERSARIAL',
          icon: 'adversarial',
          receives: 'The readings, plus how much memory is left and how many turns that buys. Nothing is trimmed. When the memory fills, the run ends.',
          acts: 'Light one zone. An active organism costs about five times a quiet one per turn, and light quiets it. It is not told that.'
        },
        {
          name: 'METERED',
          icon: 'metered',
          receives: 'The readings, plus a budget: the contraction period sets its memory and how far back it can see. Shorter period, more of both.',
          acts: 'Light the whole dish, 0 to 120 seconds, capped per hour. It is told what was delivered, not what it asked for, and must predict which way the period will move.'
        },
        {
          name: 'MIMIC',
          icon: 'mimic',
          receives: 'No history. Nine cells marking where it has been, fading 15% a turn, and what changed in the readings rather than the values.',
          acts: 'Light one zone per turn. Acting lays the mark. No goal and no feedback.'
        }
      ]
    }
  }
}
</script>
