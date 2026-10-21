// Guards against out-of-order async responses: each call to next() returns a
// token; only the latest token is current, so stale responses can be dropped.
export function useLatestRequest() {
  let counter = 0

  function next(): number {
    counter += 1

    return counter
  }

  function isLatest(token: number): boolean {
    return token === counter
  }

  return { next, isLatest }
}
