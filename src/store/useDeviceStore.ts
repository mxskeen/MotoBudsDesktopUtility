import { create } from 'zustand';

export interface DeviceState {
  connected: boolean;
  modelId: string | null;
  name: string | null;
  features: number[];
  battery: {
    left: number | null;
    right: number | null;
    case: number | null;
    chargingL: boolean;
    chargingR: boolean;
    chargingCase: boolean;
    inCaseL: boolean;
    inCaseR: boolean;
  };
  ancMode: number;
  eqBands: number[];
  eqPreset: string;
  hiRes: boolean;
  gameMode: boolean;
  inEarFeatureEnabled: boolean;
  physicallyInEarL: boolean;
  physicallyInEarR: boolean;
  volBoost: boolean;
  fitTestRunning: boolean;
  fitTestResultL: number | null;
  fitTestResultR: number | null;
  fmdLeft: boolean;
  fmdRight: boolean;
  gestures: {
    left: Record<number, number>;
    right: Record<number, number>;
  };
  currentView: 'main' | 'sound' | 'gestures' | 'more' | 'fit-test' | 'ring-earbuds' | 'equalizer';
  reconnectStatus: 'idle' | 'dropping' | 'reconnecting' | 'success';
  minimizeToTray: boolean;
  
  // Actions
  setDevice: (data: any) => void;
  setConnected: (status: boolean) => void;
  disconnect: () => void;
  updateStateFromPdu: (pdu: any) => void;
  setAncMode: (mode: number, subMode: number) => void;
  setEqBands: (bands: number[]) => void;
  setEqPreset: (preset: string) => void;
  setGameMode: (enabled: boolean) => void;
  setHiRes: (enabled: boolean) => void;
  setInEarFeature: (enabled: boolean) => void;
  setVolBoost: (enabled: boolean) => void;
  setFmd: (left: boolean, right: boolean) => void;
  setGestureConfig: (earbud: number, gestureType: number, func: number) => void;
  setCurrentView: (view: 'main' | 'sound' | 'gestures' | 'more' | 'fit-test' | 'ring-earbuds' | 'equalizer') => void;
  setReconnectStatus: (status: 'idle' | 'dropping' | 'reconnecting' | 'success') => void;
  setMinimizeToTray: (enabled: boolean) => void;
}

export interface SavedSettings {
  ancMode?: number;
  gameMode?: boolean;
  hiRes?: boolean;
  volBoost?: boolean;
  inEarFeatureEnabled?: boolean;
  eqBands?: number[];
  eqPreset?: string;
  gestures?: {
    left: Record<number, number>;
    right: Record<number, number>;
  };
}

export const loadSavedSettings = (): SavedSettings | null => {
  try {
    const raw = localStorage.getItem('moto_buds_preferences');
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return null;
};

export const saveSettings = (partial: Partial<SavedSettings>) => {
  try {
    const current = loadSavedSettings() || {};
    const updated = { ...current, ...partial };
    localStorage.setItem('moto_buds_preferences', JSON.stringify(updated));
  } catch (e) {}
};

export const applySavedSettingsToDevice = async () => {
  const saved = loadSavedSettings();
  if (!saved || !(window as any).api || !(window as any).api.motoCommand) return;

  try {
    // 1. ANC Mode
    if (saved.ancMode !== undefined) {
      await (window as any).api.motoCommand({ op: 'anc', mode: saved.ancMode });
    }

    // 2. Game Mode
    if (saved.gameMode !== undefined) {
      await (window as any).api.motoCommand({ op: 'game', enabled: saved.gameMode ? 1 : 0 });
    }

    // 3. Hi-Res Mode
    if (saved.hiRes !== undefined) {
      await (window as any).api.motoCommand({ op: 'hires', enabled: saved.hiRes ? 1 : 0 });
    }

    // 4. Volume Boost
    if (saved.volBoost !== undefined) {
      await (window as any).api.motoCommand({ op: 'volboost', enabled: saved.volBoost ? 1 : 0 });
    }

    // 5. In-Ear Detection
    if (saved.inEarFeatureEnabled !== undefined) {
      await (window as any).api.motoCommand({ op: 'inear', enabled: saved.inEarFeatureEnabled ? 1 : 0 });
    }

    // 6. Custom EQ
    if (saved.eqBands && saved.eqBands.length === 10) {
      await (window as any).api.motoCommand({ op: 'eq', bands: saved.eqBands });
    }

    // 7. Gestures
    if (saved.gestures) {
      if (saved.gestures.left) {
        for (const [gt, fn] of Object.entries(saved.gestures.left)) {
          await (window as any).api.motoCommand({ op: 'gesture', earbud: 0, gesture: parseInt(gt), func: fn });
        }
      }
      if (saved.gestures.right) {
        for (const [gt, fn] of Object.entries(saved.gestures.right)) {
          await (window as any).api.motoCommand({ op: 'gesture', earbud: 1, gesture: parseInt(gt), func: fn });
        }
      }
    }
  } catch (e) {
    console.error("Failed to auto-apply saved settings to device:", e);
  }
};

const initialSaved = loadSavedSettings();

export const useDeviceStore = create<DeviceState>((set, get) => ({
  connected: false,
  modelId: null,
  name: null,
  features: [],
  battery: { left: null, right: null, case: null, chargingL: false, chargingR: false, chargingCase: false, inCaseL: false, inCaseR: false },
  ancMode: initialSaved?.ancMode !== undefined ? initialSaved.ancMode : 0,
  ancSubMode: 0,
  eqBands: initialSaved?.eqBands || [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  eqPreset: initialSaved?.eqPreset || 'Custom EQ',
  hiRes: initialSaved?.hiRes ?? false,
  gameMode: initialSaved?.gameMode ?? false,
  inEarFeatureEnabled: initialSaved?.inEarFeatureEnabled ?? false,
  physicallyInEarL: true,
  physicallyInEarR: true,
  volBoost: initialSaved?.volBoost ?? false,
  fitTestRunning: false,
  fitTestResultL: null,
  fitTestResultR: null,
  fmdLeft: false,
  fmdRight: false,
  gestures: initialSaved?.gestures || { left: {}, right: {} },
  currentView: 'main',
  reconnectStatus: 'idle',
  minimizeToTray: localStorage.getItem('minimizeToTray') === 'true',

  setCurrentView: (view) => set({ currentView: view }),
  setReconnectStatus: (status) => set({ reconnectStatus: status }),

  setDevice: (data) => set({
    modelId: data.modelId,
    name: data.name,
    features: data.features,
    battery: data.battery
  }),

  setConnected: (status) => set({ connected: status }),

  disconnect: () => set({
    connected: false,
    modelId: null,
    name: null,
    features: [],
  }),

  updateStateFromPdu: (pdu) => set(() => {
    switch (pdu.opcode) {
      case 0: // Profile Version / Firmware Info
        try {
          const str = new TextDecoder().decode(new Uint8Array(pdu.payload));
          // Strings are likely null-terminated or delimited. Let's just find the first XT... string.
          const match = str.match(/(XT\d{4}-\d)/);
          
          let nameStr = "Moto Buds";
          if (str.toLowerCase().includes("moto buds bass")) nameStr = "Moto Buds Bass";
          else if (str.toLowerCase().includes("moto buds+")) nameStr = "Moto Buds+";
          
          if (match) {
            return { modelId: match[1], name: nameStr };
          } else if (nameStr !== "Moto Buds") {
            return { name: nameStr };
          }
        } catch (e) {}
        break;
      case 5: // Battery
      case 9: // Battery notification
      case 11: // Async Battery Notification (from diagnostics)
        if (pdu.payload.length >= 3) {
          const rawLeft = pdu.payload[0];
          const rawRight = pdu.payload[1];
          const rawCase = pdu.payload[2];
          
          const currentBattery = get().battery;
          return {
            battery: {
              ...currentBattery,
              left: (rawLeft & 0x7F) > 100 ? null : (rawLeft & 0x7F),
              right: (rawRight & 0x7F) > 100 ? null : (rawRight & 0x7F),
              case: (rawCase & 0x7F) > 100 ? null : (rawCase & 0x7F),
              chargingL: (rawLeft & 0x80) > 0,
              chargingR: (rawRight & 0x80) > 0,
              chargingCase: (rawCase & 0x80) > 0,
              inCaseL: (rawLeft & 0x80) > 0 ? true : currentBattery.inCaseL,
              inCaseR: (rawRight & 0x80) > 0 ? true : currentBattery.inCaseR,
            }
          };
        }
        break;
      case 512: // Read ANC mode
      case 516: // ANC changed notification
        if (pdu.payload.length >= 2) {
          return { ancMode: pdu.payload[0], ancSubMode: pdu.payload[1] };
        }
        break;
      case 768: // Read EQ
      case 770: // EQ changed
        if (pdu.payload.length >= 1) return { eqState: pdu.payload[0] };
        break;
      case 780:
      case 781: // Hi-Res
      case 785:
        if (pdu.payload.length >= 2) return { hiRes: pdu.payload[1] === 1 };
        else if (pdu.payload.length === 1) return { hiRes: pdu.payload[0] === 1 };
        break;
      case 782:
      case 786: // Game Mode
        if (pdu.payload.length >= 1) return { gameMode: pdu.payload[0] === 1 || pdu.payload[0] === 0x19 };
        break;
      case 787:
      case 789: // Volume Booster
        if (pdu.payload.length >= 1) return { volBoost: pdu.payload[0] === 1 || pdu.payload[0] === 0x1D };
        break;
      case 1026:
      case 1027: // Write response
        if (pdu.payload.length >= 1) return { inEarFeatureEnabled: pdu.payload[0] === 1 };
        break;
      case 1028:
        if (pdu.payload.length >= 2) {
           return { 
              physicallyInEarL: pdu.payload[0] === 1, 
              physicallyInEarR: pdu.payload[1] === 1 
           };
        }
        break;
      case 1036: // In-Case Status Notification
        if (pdu.payload.length >= 2) {
           const currentBattery = get().battery;
           return {
             battery: {
               ...currentBattery,
               inCaseL: pdu.payload[0] === 1,
               inCaseR: pdu.payload[1] === 1
             }
           };
        }
        break;
      case 1024: // Fit Test Start/Stop
        if (pdu.payload.length >= 1) return { fitTestRunning: pdu.payload[0] === 1, fitTestResultL: null, fitTestResultR: null };
        break;
      case 1025: // Fit Test Result
        if (pdu.payload.length >= 2) return { fitTestResultL: pdu.payload[0], fitTestResultR: pdu.payload[1], fitTestRunning: false };
        break;
      case 1038: // FMD State Notification
        if (pdu.payload.length >= 2) return { fmdLeft: pdu.payload[0] === 1, fmdRight: pdu.payload[1] === 1 };
        break;
      case 256: // Get Toggle Configs
      case 261: // Toggle Configs Status Changed
        if (pdu.payload.length >= 16) {
           const newGestures = { left: {} as Record<number, number>, right: {} as Record<number, number> };
           for (let i = 0; i < 8; i += 2) {
              if (pdu.payload[i] !== 0) newGestures.left[pdu.payload[i]] = pdu.payload[i+1];
           }
           for (let i = 8; i < 16; i += 2) {
              if (pdu.payload[i] !== 0) newGestures.right[pdu.payload[i]] = pdu.payload[i+1];
           }
           return { gestures: newGestures };
        } else if (pdu.payload.length === 3) {
           const currentGestures = get().gestures;
           const earbud = pdu.payload[0];
           const gesture = pdu.payload[1];
           const func = pdu.payload[2];
           if (earbud === 0) {
              return { gestures: { ...currentGestures, left: { ...currentGestures.left, [gesture]: func } } };
           } else {
              return { gestures: { ...currentGestures, right: { ...currentGestures.right, [gesture]: func } } };
           }
        }
        break;
    }
    return {};
  }),

  setAncMode: (mode, subMode) => {
    set({ ancMode: mode });
    saveSettings({ ancMode: mode });
    if ((window as any).sendOpcodeToDevice) {
      (window as any).sendOpcodeToDevice(513, [mode, subMode]);
    }
  },

  setEqBands: (bands) => {
    set({ eqBands: bands });
    saveSettings({ eqBands: bands });
    if ((window as any).api && (window as any).api.motoCommand) {
      (window as any).api.motoCommand({ op: 'eq', bands });
    }
  },

  setEqPreset: (preset) => {
    set({ eqPreset: preset });
    saveSettings({ eqPreset: preset });
  },

  setGameMode: (enabled) => {
    set({ gameMode: enabled });
    saveSettings({ gameMode: enabled });
    if ((window as any).sendOpcodeToDevice) {
      (window as any).sendOpcodeToDevice(783, [enabled ? 1 : 0]);
    }
  },

  setHiRes: (enabled) => {
    set({ hiRes: enabled });
    saveSettings({ hiRes: enabled });
    if ((window as any).sendOpcodeToDevice) {
      (window as any).sendOpcodeToDevice(781, [enabled ? 1 : 0]);
    }
  },

  setInEarFeature: (enabled) => {
    set({ inEarFeatureEnabled: enabled });
    saveSettings({ inEarFeatureEnabled: enabled });
    if ((window as any).sendOpcodeToDevice) {
      (window as any).sendOpcodeToDevice(1027, [enabled ? 1 : 0]);
    }
  },

  setVolBoost: (enabled) => {
    set({ volBoost: enabled });
    saveSettings({ volBoost: enabled });
    if ((window as any).sendOpcodeToDevice) {
      (window as any).sendOpcodeToDevice(788, [enabled ? 1 : 0]);
    }
  },

  setFmd: (left, right) => {
    set({ fmdLeft: left, fmdRight: right });
    if ((window as any).api && (window as any).api.motoCommand) {
      (window as any).api.motoCommand({ op: 'fmd', left: left ? 1 : 0, right: right ? 1 : 0 });
    }
  },

  setGestureConfig: (earbud, gestureType, func) => {
    const currentGestures = get().gestures;
    const isLeft = earbud === 0;
    const side = isLeft ? 'left' : 'right';
    const updatedGestures = {
      ...currentGestures,
      [side]: {
        ...currentGestures[side],
        [gestureType]: func,
      },
    };
    set({ gestures: updatedGestures });
    saveSettings({ gestures: updatedGestures });
    if ((window as any).api && (window as any).api.motoCommand) {
      (window as any).api.motoCommand({ op: 'gesture', earbud, gesture: gestureType, func });
    }
  },

  setMinimizeToTray: (enabled) => {
    localStorage.setItem('minimizeToTray', enabled ? 'true' : 'false');
    set({ minimizeToTray: enabled });
    if ((window as any).api && (window as any).api.setMinimizeToTray) {
      (window as any).api.setMinimizeToTray(enabled);
    }
  },
}));

useDeviceStore.subscribe((state, prevState) => {
  if (state.battery !== prevState.battery || state.ancMode !== prevState.ancMode || state.physicallyInEarL !== prevState.physicallyInEarL || state.physicallyInEarR !== prevState.physicallyInEarR || state.name !== prevState.name) {
    if ((window as any).api && (window as any).api.updateTrayTooltip) {
      let tooltip = state.name || "Moto Buds";
      const b = state.battery;
      const parts = [
        `L: ${b.left ?? '--'}%`,
        `R: ${b.right ?? '--'}%`
      ];
      if ((b.inCaseL || b.inCaseR) && b.case !== null) {
        parts.push(`Case: ${b.case}%`);
      }
      tooltip += '\n' + parts.join(' | ');
      
      (window as any).api.updateTrayTooltip(tooltip);
      
      if ((window as any).api.updateTrayMenu) {
         (window as any).api.updateTrayMenu({
            battery: state.battery,
            ancMode: state.ancMode,
            inEarL: state.physicallyInEarL,
            inEarR: state.physicallyInEarR
         });
      }
    }
  }
});
