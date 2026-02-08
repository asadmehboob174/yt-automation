import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { QueueItem } from '@/types';

interface QueueState {
    items: QueueItem[];
    isProcessing: boolean;

    // Actions
    addItem: (item: Omit<QueueItem, 'id' | 'status' | 'createdAt'>) => void;
    removeItem: (id: string) => void;
    updateItemStatus: (id: string, status: QueueItem['status'], errorMessage?: string) => void;
    getNextItem: () => QueueItem | null;
    clearCompleted: () => void;
    setProcessing: (isProcessing: boolean) => void;
}

export const useQueueStore = create<QueueState>()(
    persist(
        (set, get) => ({
            items: [],
            isProcessing: false,

            addItem: (item) => {
                const newItem: QueueItem = {
                    ...item,
                    id: crypto.randomUUID(),
                    status: 'queued',
                    createdAt: new Date().toISOString(),
                };
                set((state) => ({ items: [...state.items, newItem] }));
            },

            removeItem: (id) => {
                set((state) => ({
                    items: state.items.filter((item) => item.id !== id),
                }));
            },

            updateItemStatus: (id, status, errorMessage) => {
                set((state) => ({
                    items: state.items.map((item) =>
                        item.id === id ? { ...item, status, errorMessage } : item
                    ),
                }));
            },

            getNextItem: () => {
                const state = get();
                return state.items.find((item) => item.status === 'queued') || null;
            },

            clearCompleted: () => {
                set((state) => ({
                    items: state.items.filter((item) => item.status !== 'done'),
                }));
            },

            setProcessing: (isProcessing) => set({ isProcessing }),
        }),
        {
            name: 'script-queue-storage',
        }
    )
);
