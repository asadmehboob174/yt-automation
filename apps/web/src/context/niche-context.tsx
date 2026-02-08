"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface Channel {
  id: string; // This corresponds to 'nicheId' from API
  name: string;
  styleSuffix?: string; // Added for styling consistency
}

interface NicheContextType {
  selectedNicheId: string;
  setSelectedNicheId: (id: string) => void;
  channels: Channel[];
  refreshChannels: () => Promise<void>;
  isLoading: boolean;
}

const NicheContext = createContext<NicheContextType | undefined>(undefined);

export function NicheProvider({ children }: { children: ReactNode }) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedNicheId, setSelectedNicheId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  const refreshChannels = async () => {
    try {
      setIsLoading(true);
      const res = await fetch("http://127.0.0.1:8000/channels");
      const data = await res.json();
      setChannels(data.channels);
      
      // Auto-select first if none selected and list not empty
      if (!selectedNicheId && data.channels.length > 0) {
        setSelectedNicheId(data.channels[0].id);
      }
    } catch (error) {
      console.error("Failed to fetch channels", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshChannels();
  }, []);

  return (
    <NicheContext.Provider 
      value={{ 
        selectedNicheId, 
        setSelectedNicheId, 
        channels, 
        refreshChannels,
        isLoading 
      }}
    >
      {children}
    </NicheContext.Provider>
  );
}

export function useNiche() {
  const context = useContext(NicheContext);
  if (context === undefined) {
    throw new Error("useNiche must be used within a NicheProvider");
  }
  return context;
}
