<template>
<div class="content">
<p class="lead opening"><span class="drop">sLLM</span> pairs a slime mould with a language
model, although this project is not really about either of them. It is a study in how to
interface two very different kinds of systems.</p>
<ul>
  <li v-show="deck.step >= 1">How do they come into contact?</li>
  <li v-show="deck.step >= 2">What do they know about each other?</li>
  <li v-show="deck.step >= 3">How do they influence each other?</li>
</ul>
</div>
<figure class="media">
<img src="/deck-media/00_SarahGrant_05_electrodes.jpeg" alt="The electrodes in the dish">
</figure>
</template>

<script>
export default {
  name: '01_sllm',
  inject: ['deck'],
  meta: {
    classes: 'split',
    section: '',
    // The three questions arrive one at a time on the right arrow.
    steps: 3,
    reg: 0.05, fx: 30, fy: 46
  }
}
</script>
