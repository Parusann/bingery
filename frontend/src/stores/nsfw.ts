import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Persisted toggle controlling whether Hentai/Ecchi-tagged anime are shown
 * across the app. Default = hidden. The backend defaults to filtering them
 * out when `include_nsfw` is missing or false, so the API client only needs
 * to opt-in (`?include_nsfw=true`) when this store says `visible`.
 */
interface NsfwState {
  visible: boolean;
  toggle: () => void;
  setVisible: (v: boolean) => void;
}

export const useNsfw = create<NsfwState>()(
  persist(
    (set) => ({
      visible: false,
      toggle: () => set((s) => ({ visible: !s.visible })),
      setVisible: (v) => set({ visible: v }),
    }),
    { name: "bingery-nsfw" }
  )
);
