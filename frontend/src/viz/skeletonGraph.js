// Turning the extracted skeleton into three electrode territories.
//
// Three electrodes on three strands is not a field, so nothing is interpolated
// across the body. Every skeleton point is assigned to exactly one electrode --
// the nearest one along the tubes -- and carries its distance from it. The
// renderer fades activity out with that distance, which handles two cases for
// free: seams between territories go dark on their own, and body no electrode
// reaches stays unlit while still being drawn.
//
// Distance is geodesic because the organism conducts along its tubes. Two
// strands can pass close on screen and be far apart through the network.

// Endpoints within this much of each other in dish coords (-1..1 across the
// dish) are the same junction. The extractor emits each tube as its own
// polyline and does not weld them, so without this the graph is 120 loose
// segments and nothing is reachable from anything.
const WELD = 0.012

const dist2 = (a, b) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

function weldNodes(edges) {
  const nodes = []
  const indexOf = (point) => {
    for (let i = 0; i < nodes.length; i++) {
      if (dist2(nodes[i], point) <= WELD * WELD) return i
    }
    nodes.push([point[0], point[1]])
    return nodes.length - 1
  }
  const links = edges.map((points) => ({
    points,
    a: indexOf(points[0]),
    b: indexOf(points[points.length - 1]),
    // Cumulative arc length at each vertex, so a point partway along a tube
    // can be placed without walking the polyline again.
    arc: points.reduce((acc, point, i) => {
      acc.push(i === 0 ? 0 : acc[i - 1] + Math.hypot(
        point[0] - points[i - 1][0], point[1] - points[i - 1][1]))
      return acc
    }, []),
  }))
  return { nodes, links }
}

function adjacency(nodeCount, links) {
  const adj = Array.from({ length: nodeCount }, () => [])
  for (const link of links) {
    const length = link.arc[link.arc.length - 1]
    if (link.a === link.b) continue
    adj[link.a].push({ to: link.b, length })
    adj[link.b].push({ to: link.a, length })
  }
  return adj
}

// Multi-source Dijkstra. Each source is an electrode; every node ends up with
// its distance to the nearest one and which one that was. A linear scan for the
// next node is fine at this size -- the skeleton is ~120 nodes, and a heap here
// would be more code than it saves.
function territories(adj, sources) {
  const distance = new Float64Array(adj.length).fill(Infinity)
  const owner = new Int8Array(adj.length).fill(-1)
  const settled = new Uint8Array(adj.length)
  sources.forEach((node, index) => {
    distance[node] = 0
    owner[node] = index
  })
  for (;;) {
    let current = -1
    let best = Infinity
    for (let i = 0; i < adj.length; i++) {
      if (!settled[i] && distance[i] < best) { best = distance[i]; current = i }
    }
    if (current < 0) break
    settled[current] = 1
    for (const edge of adj[current]) {
      const candidate = distance[current] + edge.length
      if (candidate < distance[edge.to]) {
        distance[edge.to] = candidate
        owner[edge.to] = owner[current]
      }
    }
  }
  return { distance, owner }
}

// Farthest-point sampling from the food source the extractor recorded. A
// stand-in until real electrode positions are recorded: the tips are placed on
// separate strands by hand, and spreading them out is the closest guess.
function spreadElectrodes(nodes, adj, count, origin) {
  const seed = origin
    ? nodes.reduce((best, point, i) =>
        dist2(point, origin) < dist2(nodes[best], origin) ? i : best, 0)
    : 0
  const chosen = [seed]
  while (chosen.length < count) {
    const { distance } = territories(adj, chosen)
    let best = -1
    let bestDistance = -1
    for (let i = 0; i < nodes.length; i++) {
      // Unreachable nodes are Infinity and would win every time; a strand the
      // graph cannot get to is the last place to claim an electrode sits.
      if (distance[i] !== Infinity && distance[i] > bestDistance) {
        bestDistance = distance[i]
        best = i
      }
    }
    if (best < 0) break
    chosen.push(best)
  }
  return relax(nodes, adj, chosen)
}

// Sampling alone puts two of three at the tips and leaves the seed owning four
// fifths of the body. So relax the picks: recompute territories, move each
// electrode to the node minimising the worst distance in its own, repeat. It
// settles or cycles by about the third round.
function relax(nodes, adj, chosen, rounds = 6) {
  let current = chosen.slice()
  for (let round = 0; round < rounds; round++) {
    const { owner } = territories(adj, current)
    const members = current.map((_, index) =>
      [...owner.keys()].filter((node) => owner[node] === index))
    const moved = members.map((group, index) => {
      if (group.length < 2) return current[index]
      // 1-centre of the group: the member whose farthest fellow member is
      // nearest. Distances are measured through the whole graph, not just the
      // group, because the tubes between two members may leave the territory.
      let best = current[index]
      let bestWorst = Infinity
      for (const candidate of group) {
        const { distance } = territories(adj, [candidate])
        let worst = 0
        for (const node of group) {
          if (distance[node] !== Infinity && distance[node] > worst) worst = distance[node]
        }
        if (worst < bestWorst) { bestWorst = worst; best = candidate }
      }
      return best
    })
    if (moved.every((node, index) => node === current[index])) break
    current = moved
  }
  return current
}

// Dish coordinates should be -1..1, but an extraction can overflow -- the
// placeholder reaches x = 1.20 -- and those points clip off the stage, taking
// an electrode with them. Shrink to fit only when it overflows, so real
// geometry keeps its true position.
function fitToDish(skeleton) {
  const all = []
  for (const edge of skeleton.edges || []) all.push(...edge)
  for (const point of skeleton.outline || []) all.push(point)
  if (!all.length) return skeleton
  const radius = Math.max(...all.map((p) => Math.hypot(p[0], p[1])))
  if (radius <= 1) return skeleton
  // Uniform, about the dish centre. Every distance in the graph scales by the
  // same factor, so `reach` scales with it and nothing that reads a ratio of
  // the two changes.
  const k = 1 / radius
  const scale = (point) => [point[0] * k, point[1] * k]
  return {
    ...skeleton,
    edges: (skeleton.edges || []).map((edge) => edge.map(scale)),
    outline: (skeleton.outline || []).map(scale),
    origin: skeleton.origin ? scale(skeleton.origin) : skeleton.origin,
  }
}

export function buildField(rawSkeleton, channelCount = 3) {
  const skeleton = fitToDish(rawSkeleton)
  const edges = (skeleton.edges || []).filter((points) => points.length > 1)
  const { nodes, links } = weldNodes(edges)
  const adj = adjacency(nodes.length, links)

  // `electrodes` in the skeleton file wins when it is there. It is not yet --
  // recording which node each tip actually sits on is a separate job, and
  // until it is done this view is showing plausible placement, not measured.
  const electrodes = Array.isArray(skeleton.electrodes) && skeleton.electrodes.length
    ? skeleton.electrodes.slice(0, channelCount)
    : spreadElectrodes(nodes, adj, channelCount, skeleton.origin)
  const measured = Array.isArray(skeleton.electrodes) && skeleton.electrodes.length > 0

  const { distance, owner } = territories(adj, electrodes)

  // Girth comes from distance to the food source, not the electrodes: tubes
  // thicken toward it, trunks wide and the exploratory fringe fine. Keeping it
  // independent of brightness matters -- thickness is morphology, brightness is
  // signal. Sourced from the electrodes, thick would mean 'near a probe'.
  const originNode = skeleton.origin
    ? nodes.reduce((best, point, i) =>
        dist2(point, skeleton.origin) < dist2(nodes[best], skeleton.origin) ? i : best, 0)
    : 0
  const fromOrigin = nodes.length ? territories(adj, [originNode]).distance : []
  let originReach = 0
  for (const value of fromOrigin) {
    if (value !== Infinity && value > originReach) originReach = value
  }
  originReach = originReach || 1

  // Per-vertex owner and geodesic distance. A vertex partway along a tube is
  // reached from whichever end gets there first, so both ends are tried.
  let reach = 0
  const strips = links.map((link) => {
    const length = link.arc[link.arc.length - 1]
    const perVertex = link.points.map((point, i) => {
      const fromA = distance[link.a] + link.arc[i]
      const fromB = distance[link.b] + (length - link.arc[i])
      const value = Math.min(fromA, fromB)
      const which = fromA <= fromB ? owner[link.a] : owner[link.b]
      if (value !== Infinity && value > reach) reach = value

      const originA = fromOrigin[link.a] + link.arc[i]
      const originB = fromOrigin[link.b] + (length - link.arc[i])
      const fromFood = Math.min(originA, originB)
      const girth = fromFood === Infinity
        ? 0
        : Math.pow(Math.max(0, 1 - fromFood / originReach), 1.4)

      return {
        d: value === Infinity ? -1 : value,
        owner: value === Infinity ? -1 : which,
        girth,
      }
    })
    return { points: link.points, vertices: perVertex }
  })

  // Reach per territory, not one global number: they differ by up to 7x, and a
  // single reach left the wavefront outside the small ones for most of every
  // cycle, so two channels sat dark regardless.
  const reachByOwner = new Array(channelCount).fill(0)
  for (const strip of strips) {
    for (const vertex of strip.vertices) {
      if (vertex.owner >= 0 && vertex.d > reachByOwner[vertex.owner]) {
        reachByOwner[vertex.owner] = vertex.d
      }
    }
  }
  for (let i = 0; i < reachByOwner.length; i++) {
    if (!reachByOwner[i]) reachByOwner[i] = reach || 1
  }

  return {
    nodes,
    strips,
    reachByOwner,
    electrodes: electrodes.map((node) => nodes[node]),
    electrodeNodes: electrodes,
    outline: skeleton.outline || [],
    // The longest any signal has to travel to the far end of its territory.
    // Everything in the shader that fades with distance is scaled by this, so
    // the falloff is a property of this organism rather than a tuned constant.
    reach: reach || 1,
    measured,
    placeholder: Boolean(skeleton.placeholder),
  }
}

// Resample the tubes into evenly spaced dots.
//
// Discrete points rather than strokes, deliberately: the signal is sampled at
// three places and everything between is inference.
//
// Spacing is constant along arc length, in dish units. Source polylines have
// unevenly spaced vertices, so walk by distance rather than by vertex.
export function sampleDots(field, spacing = 0.016) {
  const dots = []
  const emit = (points, vertices, kind) => {
    let carry = 0
    for (let i = 0; i < points.length - 1; i++) {
      const [x0, y0] = points[i]
      const [x1, y1] = points[i + 1]
      const length = Math.hypot(x1 - x0, y1 - y0)
      if (length <= 0) continue
      const a = vertices[i]
      const b = vertices[i + 1]
      for (let along = carry; along < length; along += spacing) {
        const t = along / length
        // Owner is taken from the nearer end rather than interpolated: a dot
        // belongs to one electrode or the other, never to a blend of two.
        const near = t < 0.5 ? a : b
        dots.push({
          x: x0 + (x1 - x0) * t,
          y: y0 + (y1 - y0) * t,
          d: a.d < 0 || b.d < 0 ? -1 : a.d + (b.d - a.d) * t,
          owner: near.owner,
          girth: (a.girth ?? 0) + ((b.girth ?? 0) - (a.girth ?? 0)) * t,
          kind,
        })
      }
      // Carry the leftover into the next segment so spacing does not reset at
      // every vertex and bunch the dots up on the curves.
      carry = spacing - ((length - carry) % spacing)
    }
  }

  for (const strip of field.strips) emit(strip.points, strip.vertices, 'tube')
  if (field.outline?.length) {
    const loop = field.outline.concat([field.outline[0]])
    emit(loop, loop.map(() => ({ d: -1, owner: -1, girth: 0 })), 'outline')
  }
  return dots
}
