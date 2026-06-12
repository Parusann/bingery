import "@testing-library/jest-dom/vitest";

if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}

// jsdom has no matchMedia; useIsDesktop (Modal bottom-sheet branching)
// needs it. Default to desktop so components behave like the wide
// viewport the original tests were written against.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: query.includes("min-width"),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// Node 22+ ships an experimental built-in `localStorage` global that requires
// `--localstorage-file=<path>` to function. Without it, calls like
// `localStorage.clear()` throw "is not a function". We replace it with an
// in-memory Storage-compatible shim so tests work in any Node version.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() { return this.store.size; }
  clear(): void { this.store.clear(); }
  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null;
  }
  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
  removeItem(key: string): void { this.store.delete(key); }
  setItem(key: string, value: string): void { this.store.set(key, String(value)); }
}

const memStorage = new MemoryStorage();
Object.defineProperty(globalThis, "localStorage", {
  value: memStorage,
  configurable: true,
  writable: true,
});
if (typeof window !== "undefined") {
  Object.defineProperty(window, "localStorage", {
    value: memStorage,
    configurable: true,
    writable: true,
  });
}
