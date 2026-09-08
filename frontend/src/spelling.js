// "mould" or "mold", by the reader's own locale rather than by geography.
//
// navigator.language is the setting the visitor chose, needs no lookup service
// and leaves the page working offline. US English is the only major variety
// that drops the u; Canadian and Australian English keep it.
const US = /^en[-_](US|PH)$/i

function american() {
  const tags = navigator.languages && navigator.languages.length
    ? navigator.languages
    : [navigator.language || 'en']
  // The first English tag decides. A visitor whose first language is not
  // English but who falls back to en-US still reads US spelling.
  for (const tag of tags) {
    if (/^en\b/i.test(tag) || /^en[-_]/i.test(tag)) return US.test(tag)
  }
  return false
}

export const MOULD = american() ? 'mold' : 'mould'
export const MOULD_CAP = american() ? 'Mold' : 'Mould'
