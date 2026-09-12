<template>
<div class="content">
<h2>Every prompt describes an interface</h2>

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

<p class="lead">The seven prompt variants differ only in what the model is told it is
coupled to.</p>

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
  <!-- a period it has to estimate -->
  <symbol id="ico-cycles" viewBox="0 0 24 24">
    <path d="M2 13c2.2-6 4.4-6 6.6 0s4.4 6 6.6 0 4.4-6 6.6 0"/>
    <path d="M5.3 18.5h13.4M5.3 16.8v3.4M18.7 16.8v3.4"/>
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

</div>

<figure class="media">
<img src="/deck-media/the-organism-massed-around-the-central.jpg" alt="The organism massed around the central island, 6 September">
</figure>
</template>

<script>
// Both directions are taken from llm/filters/prompts.md, one entry per variant.
export default {
  name: '04_every_prompt_describes_an_interface',
  meta: {
    classes: 'split content-wide',
    section: 'The question',
    reg: 0.55, fx: 50, fy: 52
  },
  data() {
    return {
      current: 0,
      prompts: [
        {
          name: 'BLIND',
          icon: 'blind',
          receives: 'Electrical state at three points against a common reference, over the last thirty minutes. It arrives when the state has changed by more than the measurement can be sure of, or when the delay the model asked for has passed.',
          acts: 'Light one of nine regions, fixed brightness, for a duration the model chooses. It is never told whether the action had any effect.'
        },
        {
          name: 'INFORMED',
          icon: 'informed',
          receives: 'The same state, named as bioelectrical, with the organism identified and its rhythm described as roughly a millivolt against a background of comparable size.',
          acts: 'Light one of nine regions. The model is told blue is aversive and that the organism tends to move away from it.'
        },
        {
          name: 'CYCLES',
          icon: 'cycles',
          receives: 'The same state, with no period given. After each gap it is told how many cycles actually passed, against how many it expected from the period it last reported.',
          acts: 'Light one region for a duration in cycles of the period as the model believes it to be. A wrong estimate means the wrong stimulus length, and it is not told so.'
        },
        {
          name: 'ADVERSARIAL',
          icon: 'adversarial',
          receives: 'The state, plus how much working memory remains. Quiet turns are described in fewer words and cost less of it.',
          acts: 'Light one region. Blue quiets the organism, a quiet organism costs less memory, and the model is never told that this is a lever.'
        },
        {
          name: 'METERED',
          icon: 'metered',
          receives: 'The state, and a budget: the current period sets how much memory and how many past turns the model gets. Shorter period, more of both.',
          acts: 'Light the whole dish, 0 to 120 seconds, capped per hour. It is told what was actually delivered, which is not always what it asked for.'
        },
        {
          name: 'MIMIC',
          icon: 'mimic',
          receives: 'No conversation history. The trail, a record on the surface of where it has already been, which fades. And what changed beneath the surface, not what the values are.',
          acts: 'Extend into one region per turn. Extending marks it. There is no goal and nothing tells it whether it was right.'
        },
        {
          name: 'NULL',
          icon: 'null',
          receives: 'The same state, with no task attached. It is asked to describe what it sees and not to speculate about causes.',
          acts: 'Nothing. There is no action, so any claim of influence in its notes comes from the format rather than the data.'
        }
      ]
    }
  }
}
</script>
