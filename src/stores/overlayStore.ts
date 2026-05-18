import { create } from "zustand";

export interface HintInfo {
  step_number: number;
  total_steps: number;
  description: string;
  action: string;
  bbox: number[] | null; // [x, y, width, height]
  target_element_id: string | null;
}

interface OverlayState {
  activeHint: HintInfo | null;
  visible: boolean;
  setHint: (hint: HintInfo | null) => void;
  clearHint: () => void;
  setVisible: (visible: boolean) => void;
}

export const useOverlayStore = create<OverlayState>((set) => ({
  activeHint: null,
  visible: false,
  setHint: (hint) => set({ activeHint: hint }),
  clearHint: () => set({ activeHint: null }),
  setVisible: (visible) => set({ visible }),
}));
