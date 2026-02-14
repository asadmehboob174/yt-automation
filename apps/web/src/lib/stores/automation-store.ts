import { create } from 'zustand';
import type { AutomationStep, AutomationStepStatus } from '@/types';
import { api } from '@/lib/api';
import { useProjectStore } from '@/lib/stores/project-store';

const AUTOMATION_STEPS = [
    'Parsing script',
    'Extracting characters',
    'Generating character images',
    'Generating scene images',
    'Generating scene videos',
    'Selecting music',
    'Stitching final video',
];

interface AutomationState {
    isRunning: boolean;
    currentStepIndex: number;
    progress: number;
    steps: AutomationStep[];
    currentAction: string;
    cancelled: boolean;

    // Actions
    // Actions
    startAutomation: (script: string, channelId: string, format: 'short' | 'long', autoUpload?: boolean, preparedBreakdown?: any) => Promise<string | null>;
    cancelAutomation: () => void;
    updateStep: (index: number, status: AutomationStepStatus, message?: string) => void;
    updateProgress: (action: string) => void;
    reset: () => void;
}

const createInitialSteps = (): AutomationStep[] =>
    AUTOMATION_STEPS.map((name) => ({
        name,
        status: 'pending' as AutomationStepStatus,
    }));

const ensureString = (val: any): string => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    return JSON.stringify(val);
};

export const useAutomationStore = create<AutomationState>((set, get) => ({
    isRunning: false,
    currentStepIndex: 0,
    progress: 0,
    steps: createInitialSteps(),
    currentAction: '',
    cancelled: false,

    updateStep: (index, status, message) => {
        set((state) => ({
            steps: state.steps.map((step, i) =>
                i === index
                    ? { ...step, status, errorMessage: message }
                    : step
            ),
            currentStepIndex: index,
            progress: Math.round(((index + (status === 'done' ? 1 : 0.5)) / AUTOMATION_STEPS.length) * 100),
        }));
    },

    updateProgress: (action) => {
        set({ currentAction: action });
    },

    cancelAutomation: () => {
        set({ cancelled: true, isRunning: false, currentAction: 'Cancelled by user' });
    },

    reset: () => {
        set({
            isRunning: false,
            currentStepIndex: 0,
            progress: 0,
            steps: createInitialSteps(),
            currentAction: '',
            cancelled: false,
        });
    },

    startAutomation: async (script, channelId, format, autoUpload = false, preparedBreakdown = null) => {
        const { updateStep, updateProgress, reset } = get();
        reset();
        set({ isRunning: true, cancelled: false });

        try {
            // Step 1: Parse script
            updateStep(0, 'running');
            let breakdown: any;

            if (preparedBreakdown) {
                updateProgress('Using provided JSON script...');
                breakdown = preparedBreakdown;
                // Simulate small delay for UX
                await new Promise(r => setTimeout(r, 500));
            } else {
                updateProgress('Sending script to backend...');
                breakdown = await api.post<any>('/scripts/generate-breakdown', {
                    story_narrative: script,
                    niche_id: channelId,
                    video_length: format,  // 'short' or 'long'
                    video_type: 'story',   // Default to 'story' for 1-click automation
                });
            }

            if (get().cancelled) return null;
            updateStep(0, 'done');

            // Navigate to Script tab (Step 1) to show parsing complete
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            useProjectStore.getState().setBreakdown(breakdown as any);
            useProjectStore.getState().setStep(1);

            // Step 2: Extract characters
            updateStep(1, 'running');
            updateProgress(`Found ${breakdown.characters.length} characters`);
            const characters = breakdown.characters;
            updateStep(1, 'done');

            if (get().cancelled) return null;

            // Step 3: Generate character images (streaming + session reuse)
            // Navigate to Characters tab (Step 2) so user can see progress
            useProjectStore.getState().setStep(2);
            updateStep(2, 'running');
            const characterImages: Array<{ name: string; imageUrl: string }> = [];

            const charactersToGenerate = characters.map((c: any, i: number) => ({
                index: i,
                name: c.name,
                prompt: c.prompt,
            }));

            console.log('--- Step: Character Generation ---');
            console.log('Characters found:', characters.length, characters);
            updateProgress(`Starting batch generation for ${characters.length} character images...`);

            if (characters.length === 0) {
                console.warn('⚠️ No characters found to generate. Skipping to scenes.');
                updateProgress('No characters found in script. Skipping character generation.');
            } else {
                const charResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/characters/generate-images-stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        niche_id: channelId,
                        characters: charactersToGenerate, // Reusing field name from scene request for simplicity
                        video_type: format === 'short' ? 'shorts' : 'story',
                    }),
                });

                if (!charResponse.ok) {
                    const error = await charResponse.json().catch(() => ({ detail: 'Unknown error' }));
                    console.error('Character generation failed:', error);
                    updateProgress(`⚠️ Character generation failed: ${JSON.stringify(error.detail || error)}`);
                    // We don't throw here to allow scenes to generate even if characters fail
                } else if (charResponse.body) {
                    const charReader = charResponse.body.getReader();
                    const charDecoder = new TextDecoder();
                    let charBuffer = '';

                    try {
                        while (true) {
                            const { done, value } = await charReader.read();
                            if (done) break;
                            if (get().cancelled) {
                                await charReader.cancel();
                                return null;
                            }

                            charBuffer += charDecoder.decode(value, { stream: true });
                            const lines = charBuffer.split('\n');
                            charBuffer = lines.pop() || '';

                            for (const line of lines) {
                                if (!line.trim()) continue;
                                try {
                                    const result = JSON.parse(line);
                                    console.log('Character stream result:', result);

                                    if (result.error) {
                                        console.error(`Error in character stream line: ${result.error}`);
                                        continue;
                                    }

                                    const { index, imageUrl } = result;
                                    if (imageUrl) {
                                        const charName = characters[index].name;
                                        updateProgress(`Character ${charName} image generated.`);
                                        characterImages.push({ name: charName, imageUrl });

                                        // Update UI in real-time
                                        useProjectStore.getState().updateCharacter(index, {
                                            imageUrl: imageUrl,
                                            isLocked: true
                                        });
                                    }
                                } catch (e) {
                                    console.error('Failed to parse character stream line:', line, e);
                                }
                            }
                        }
                    } finally {
                        charReader.releaseLock();
                    }
                }
            }
            updateStep(2, 'done');

            if (get().cancelled) return null;

            // Step 4 & 5: Pipelined Image and Video Generation
            // Navigate to Scene Images tab (Step 3)
            useProjectStore.getState().setStep(3);
            updateStep(3, 'running');
            updateStep(4, 'running');
            updateProgress(`Starting pipelined image and video generation...`);

            const videoPromises = new Map<number, Promise<void>>();
            const scenesToGenerate = breakdown.scenes.map((s: any, i: number) => ({
                index: i,
                // Support both snake_case (API) and camelCase (JSON) keys
                prompt: s.text_to_image_prompt || s.textToImage || s.character_pose_prompt || s.characterPose || '',
            }));

            // Use direct fetch for streaming
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/scenes/generate-images-stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    niche_id: channelId,
                    scenes: scenesToGenerate,
                    character_images: characterImages,
                    video_type: format === 'short' ? 'shorts' : 'story',
                    thumbnail_prompt: (breakdown as any).thumbnail_prompt || null
                }),
            });

            if (!response.body) throw new Error('Failed to start image stream');
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let accumulatedBuffer = '';

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    if (get().cancelled) {
                        await reader.cancel();
                        return null;
                    }

                    accumulatedBuffer += decoder.decode(value, { stream: true });
                    const lines = accumulatedBuffer.split('\n');
                    accumulatedBuffer = lines.pop() || ''; // Keep the last partial line

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        const result = JSON.parse(line);

                        if (result.error) {
                            console.error(`Error in stream: ${result.error}`);
                            continue;
                        }

                        const { index, imageUrl, type } = result;

                        if (type === 'thumbnail' && imageUrl) {
                            console.log('Thumbnail received:', imageUrl);
                            useProjectStore.getState().setThumbnailUrl(imageUrl);
                            updateProgress('YouTube thumbnail generated successfully.');
                            continue;
                        }

                        if (imageUrl) {
                            updateProgress(`Image received for scene ${index + 1}. Starting video...`);
                            useProjectStore.getState().updateScene(index, { imageUrl });

                            // Trigger video generation concurrently
                            const videoPromise = (async () => {
                                let videoSuccess = false;
                                for (let attempt = 0; attempt < 3; attempt++) {
                                    if (get().cancelled) return;
                                    try {
                                        const sceneData = breakdown.scenes[index];
                                        const i2vPrompt = ensureString(sceneData.image_to_video_prompt || sceneData.textToVideo || sceneData.prompt);
                                        const videoResult = await api.post<{ videoUrl: string, formattedPrompt?: string, textToVideoUrl?: string }>('/scenes/generate-video', {
                                            scene_index: index,
                                            image_url: imageUrl,
                                            prompt: i2vPrompt,
                                            text_to_video_prompt: i2vPrompt, // Same prompt for T2V
                                            dialogue: ensureString(sceneData.dialogue),
                                            niche_id: channelId,
                                            is_shorts: format === 'short',
                                            camera_angle: ensureString(sceneData.camera_angle || sceneData.cameraAngle),
                                            sound_effect: sceneData.sfx || sceneData.sound_effect,
                                            emotion: ensureString(sceneData.emotion)
                                        });
                                        useProjectStore.getState().updateScene(index, {
                                            videoUrl: videoResult.videoUrl,
                                            textToVideoUrl: videoResult.textToVideoUrl,
                                            isValidVideo: true,
                                            formattedPrompt: videoResult.formattedPrompt
                                        });
                                        videoSuccess = true;
                                        break;
                                    } catch (e) {
                                        console.warn(`Retry ${attempt + 1}/3 for scene ${index} video failed:`, e);
                                        if (attempt < 2) await new Promise(r => setTimeout(r, 2000));
                                    }
                                }
                                if (!videoSuccess) {
                                    console.error(`Failed to generate video for scene ${index + 1} after 3 attempts.`);
                                }
                            })();
                            videoPromises.set(index, videoPromise);
                        }
                    }
                }
            } finally {
                reader.releaseLock();
            }

            updateStep(3, 'done');
            updateProgress('All images generated. Finishing remaining videos...');

            // Wait for all video generations to complete
            await Promise.all(Array.from(videoPromises.values()));

            if (get().cancelled) return null;

            // Video Verification and Repair
            updateProgress('Verifying video integrity...');
            const finalScenes = useProjectStore.getState().scenes;
            const finalVideoUrls: string[] = [];

            for (let i = 0; i < breakdown.scenes.length; i++) {
                let scene = useProjectStore.getState().scenes[i];
                let currentVideoUrl = scene.videoUrl;
                let isValid = false;

                // Pass 1: Initial verify for existing URL
                if (currentVideoUrl) {
                    try {
                        const verification = await api.post<{ valid: boolean }>('/videos/verify', { video_url: currentVideoUrl });
                        isValid = verification.valid;
                    } catch (e) {
                        console.error(`Verification failed for scene ${i + 1}`, e);
                    }
                }

                // Pass 2: Repair if invalid
                if (!isValid) {
                    updateProgress(`Repairing missing/corrupt video for scene ${i + 1}...`);
                    try {
                        const sceneData = breakdown.scenes[i];
                        const i2vPrompt = ensureString(sceneData.image_to_video_prompt || sceneData.textToVideo || sceneData.prompt);
                        const repairResult = await api.post<{ videoUrl: string, formattedPrompt: string, textToVideoUrl?: string }>('/scenes/generate-video', {
                            scene_index: i,
                            image_url: scene.imageUrl || '',
                            prompt: i2vPrompt,
                            text_to_video_prompt: i2vPrompt, // Same prompt for T2V
                            dialogue: ensureString(sceneData.dialogue),
                            niche_id: channelId,
                            is_shorts: format === 'short',
                            camera_angle: ensureString(sceneData.camera_angle || sceneData.cameraAngle),
                            sound_effect: sceneData.sfx || sceneData.sound_effect,
                            emotion: ensureString(sceneData.emotion)
                        });
                        currentVideoUrl = repairResult.videoUrl;

                        // RE-VERIFY immediately after repair
                        if (currentVideoUrl) {
                            const reVerify = await api.post<{ valid: boolean }>('/videos/verify', { video_url: currentVideoUrl });
                            isValid = reVerify.valid;
                            useProjectStore.getState().updateScene(i, {
                                videoUrl: currentVideoUrl,
                                isValidVideo: isValid,
                                formattedPrompt: repairResult.formattedPrompt
                            });
                        }
                    } catch (e) {
                        console.error(`Repair failed for scene ${i + 1}`, e);
                    }
                } else {
                    // Update store with valid status if not already set
                    useProjectStore.getState().updateScene(i, { isValidVideo: true });
                }

                if (isValid && currentVideoUrl) {
                    finalVideoUrls.push(currentVideoUrl);
                }
            }

            updateStep(4, 'done');
            updateProgress('All videos verified. Checking final count...');

            if (finalVideoUrls.length < breakdown.scenes.length) {
                const missingCount = breakdown.scenes.length - finalVideoUrls.length;
                throw new Error(`Automation failed: ${missingCount} videos remain missing or invalid after repair attempts.`);
            }

            if (get().cancelled) return null;

            // Step 6: Analyze script mood for music recommendation
            updateStep(5, 'running');
            updateProgress('Analyzing story mood for best background music...');

            // Aggregate script for AI music analysis
            const scriptContent = breakdown.scenes.map((s: any) =>
                (s.image_to_video_prompt || '') + '\n' + (s.dialogue || '')
            ).join('\n\n');

            const moodAnalysis = await api.post<{ mood: string }>('/scripts/analyze-mood', {
                script: scriptContent,
                title: breakdown.title || 'Untitled',
                niche: channelId,
            }).catch(() => ({ mood: 'auto' })); // Fallback to 'auto' if analysis fails

            const recommendedMood = (moodAnalysis as any).mood || 'auto';
            updateProgress(`AI recommended mood: ${recommendedMood}`);
            updateStep(5, 'done');

            if (get().cancelled) return null;

            // Step 7: Stitch final video
            // Navigate to Final Render tab (Step 5) so user can see progress
            useProjectStore.getState().setStep(5);
            updateStep(6, 'running');
            updateProgress('Stitching all videos together...');

            const finalVideo = await api.post<{ final_video_url: string, youtube_upload?: any }>('/videos/stitch', {
                video_urls: finalVideoUrls,
                niche_id: channelId,
                title: breakdown.title || 'Untitled Video',
                music: recommendedMood, // Pass the AI recommended mood
                is_shorts: format === 'short',
                script: scriptContent, // Pass full script for context
                auto_upload: autoUpload,
                thumbnail_url: useProjectStore.getState().thumbnailUrl,
                youtube_upload: (breakdown as any).youtube_upload,
                final_assembly: (breakdown as any).final_assembly,
            });
            updateStep(6, 'done');

            // Send success email
            updateProgress('Sending notification email...');
            await api.post('/notifications/email', {
                type: 'success',
                project_name: breakdown.title || 'Untitled Video',
                video_url: finalVideo.final_video_url,
            }).catch(() => { }); // Don't fail if email fails

            set({ isRunning: false, progress: 100, currentAction: 'Complete!' });

            // Update UI with final video URL so it displays in the player
            useProjectStore.getState().setFinalVideoUrl(finalVideo.final_video_url);

            return finalVideo.final_video_url;

        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            const currentStep = get().currentStepIndex;
            get().updateStep(currentStep, 'error', errorMessage);

            // Send error email
            await api.post('/notifications/email', {
                type: 'error',
                project_name: 'Video Generation',
                error_message: errorMessage,
            }).catch(() => { });

            set({ isRunning: false, currentAction: `Error: ${errorMessage}` });
            return null;
        }
    },
}));
