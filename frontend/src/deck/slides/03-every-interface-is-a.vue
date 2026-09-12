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
    <span>{{ p.note }}</span>
  </button>
</div>
</div>

<figure class="media">
<img src="/deck-media/the-organism-massed-around-the-central.jpg" alt="The organism massed around the central island, 6 September">
</figure>
</template>

<script>
// Both directions are taken from llm/filters/prompts.md, one entry per variant.
export default {
  name: '03_every_interface_is_a',
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
          note: 'The interface and nothing else. Never told what it is coupled to.',
          receives: 'Electrical state at three points against a common reference, over the last thirty minutes. It arrives when the state has changed by more than the measurement can be sure of, or when the delay the model asked for has passed.',
          acts: 'Light one of nine regions, fixed brightness, for a duration the model chooses. It is never told whether the action had any effect.'
        },
        {
          name: 'INFORMED',
          note: "Same interface, plus the organism's name.",
          receives: 'The same state, named as bioelectrical, with the organism identified and its rhythm described as roughly a millivolt against a background of comparable size.',
          acts: 'Light one of nine regions. The model is told blue is aversive and that the organism tends to move away from it.'
        },
        {
          name: 'CYCLES',
          note: 'The period is withheld. Every duration uses the estimate it made.',
          receives: 'The same state, with no period given. After each gap it is told how many cycles actually passed, against how many it expected from the period it last reported.',
          acts: 'Light one region for a duration in cycles of the period as the model believes it to be. A wrong estimate means the wrong stimulus length, and it is not told so.'
        },
        {
          name: 'ADVERSARIAL',
          note: "The organism's activity consumes the model's context.",
          receives: 'The state, plus how much working memory remains. Quiet turns are described in fewer words and cost less of it.',
          acts: 'Light one region. Blue quiets the organism, a quiet organism costs less memory, and the model is never told that this is a lever.'
        },
        {
          name: 'METERED',
          note: "The organism's period sets the memory budget.",
          receives: 'The state, and a budget: the current period sets how much memory and how many past turns the model gets. Shorter period, more of both.',
          acts: 'Light the whole dish, 0 to 120 seconds, capped per hour. It is told what was actually delivered, which is not always what it asked for.'
        },
        {
          name: 'MIMIC',
          note: 'No history. A decaying trail on the surface instead.',
          receives: 'No conversation history. The trail, a record on the surface of where it has already been, which fades. And what changed beneath the surface, not what the values are.',
          acts: 'Extend into one region per turn. Extending marks it. There is no goal and nothing tells it whether it was right.'
        },
        {
          name: 'NULL',
          note: 'BLIND with the task removed.',
          receives: 'The same state, with no task attached. It is asked to describe what it sees and not to speculate about causes.',
          acts: 'Nothing. There is no action, so any claim of influence in its notes comes from the format rather than the data.'
        }
      ]
    }
  }
}
</script>
