import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Character, Scene, ScriptBreakdown } from '@/types';

export type ProjectStep = 1 | 2 | 3 | 4 | 5;

interface ProjectState {
    // Current step in the wizard
    currentStep: ProjectStep;

    // Project settings
    channelId: string;
    format: 'short' | 'long';
    type: 'story' | 'documentary';

    // Script data
    topic: string;
    narrative: string;
    breakdown: ScriptBreakdown | null;

    // Characters with generation status
    characters: Character[];

    // Scenes with image/video status
    scenes: Scene[];

    // Final video
    finalVideoUrl: string | null;

    // Actions
    setStep: (step: ProjectStep) => void;
    setSettings: (settings: { channelId: string; format: 'short' | 'long'; type: 'story' | 'documentary' }) => void;
    setTopic: (topic: string) => void;
    setNarrative: (narrative: string) => void;
    setBreakdown: (breakdown: ScriptBreakdown) => void;
    updateCharacter: (index: number, updates: Partial<Character>) => void;
    updateScene: (index: number, updates: Partial<Scene>) => void;
    setFinalVideoUrl: (url: string) => void;
    reset: () => void;
    canProceed: () => boolean;
}

const initialState = {
    currentStep: 1 as ProjectStep,
    channelId: '',
    format: 'short' as const,
    type: 'story' as const,
    topic: '',
    narrative: '',
    breakdown: null,
    characters: [],
    scenes: [],
    finalVideoUrl: null,
};

export const useProjectStore = create<ProjectState>()(
    persist(
        (set, get) => ({
            ...initialState,

            setStep: (step) => set({ currentStep: step }),

            setSettings: (settings) => set(settings),

            setTopic: (topic) => set({ topic }),

            setNarrative: (narrative) => set({ narrative }),

            setBreakdown: (breakdown) => {
                // Map API snake_case fields to frontend camelCase
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const apiBreakdown = breakdown as any;

                const mappedCharacters = (apiBreakdown.characters || []).map((c: Record<string, unknown>, i: number) => ({
                    id: c.id || `char-${i}`,
                    channelId: '',
                    name: c.name || '',
                    prompt: c.prompt || '',
                    imageUrl: c.imageUrl || c.image_url || undefined,
                    isLocked: c.isLocked || c.locked || false,
                }));

                const mappedScenes = (apiBreakdown.scenes || []).map((s: Record<string, unknown>, i: number) => ({
                    index: i,
                    // Map title from various possible field names
                    title: s.title || s.scene_title || '',
                    // Map text-to-image prompt
                    textToImage: s.textToImage || s.text_to_image_prompt || s.character_pose_prompt || '',
                    // Map text-to-video/motion prompt
                    textToVideo: s.textToVideo || s.image_to_video_prompt || s.motion_description || '',
                    // Map dialogue
                    dialogue: s.dialogue || s.voiceover_text || undefined,
                    // Map shot type
                    shotType: s.shotType || s.camera_angle || undefined,
                    // Existing URLs
                    imageUrl: s.imageUrl || s.image_url || undefined,
                    videoUrl: s.videoUrl || s.video_url || undefined,
                }));

                set({
                    breakdown,
                    characters: mappedCharacters,
                    scenes: mappedScenes,
                });
            },

            updateCharacter: (index, updates) => set((state) => ({
                characters: state.characters.map((c, i) =>
                    i === index ? { ...c, ...updates } : c
                ),
            })),

            updateScene: (index, updates) => set((state) => ({
                scenes: state.scenes.map((s, i) =>
                    i === index ? { ...s, ...updates } : s
                ),
            })),

            setFinalVideoUrl: (url) => set({ finalVideoUrl: url }),

            reset: () => set(initialState),

            canProceed: () => {
                const state = get();
                switch (state.currentStep) {
                    case 1:
                        return !!state.breakdown;
                    case 2:
                        return state.characters.every((c) => c.isLocked && c.imageUrl);
                    case 3:
                        return state.scenes.every((s) => s.imageUrl);
                    case 4:
                        return state.scenes.every((s) => s.videoUrl);
                    case 5:
                        return !!state.finalVideoUrl;
                    default:
                        return false;
                }
            },
        }),
        {
            name: 'video-project-storage',
            partialize: (state) => ({
                channelId: state.channelId,
                format: state.format,
                type: state.type,
                topic: state.topic,
                narrative: state.narrative,
                breakdown: state.breakdown,
                characters: state.characters,
                scenes: state.scenes,
                currentStep: state.currentStep,
            }),
        }
    )
);
