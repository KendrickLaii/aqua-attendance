export function createRequestGate() {
  let generation = 0;
  return {
    start() {
      const id = ++generation;
      return {
        isCurrent() {
          return id === generation;
        },
      };
    },
  };
}
