'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
    ChevronRight,
    ChevronLeft,
    Wand2,
    Loader2,
    Lock,
    Unlock,
    Image as ImageIcon,
    Film,
    Play,
    Upload,
    Rocket,
    CheckCircle2,
    XCircle,
    Clock,
    ImagePlus,
    Video,
    Youtube,
    FileJson,
    AlertCircle
} from 'lucide-react';
import { useProjectStore } from '@/lib/stores/project-store';
import { useAutomationStore } from '@/lib/stores/automation-store';
import { db, api } from '@/lib/api';
import type { Channel, ScriptBreakdown } from '@/types';
import { toast } from 'sonner';
import { useState, useEffect, useRef } from 'react';

const STEPS = [
    { number: 1, title: 'Script', icon: Wand2 },
    { number: 2, title: 'Characters', icon: ImageIcon },
    { number: 3, title: 'Scene Images', icon: ImagePlus },
    { number: 4, title: 'Scene Videos', icon: Video },
    { number: 5, title: 'Final', icon: Film },
];

// Helper to format timeline (0-2s) or (0:02-0:04) to [00:00-00:02]
const formatTimeline = (text: string): string => {
    if (!text) return "";
    // Match (M:SS-M:SS) or (SS-SS)
    const pattern = /[(\[]([\d:]+)(?:s)?-([\d:]+)(?:s)?[)\]]/g;
    return text.replace(pattern, (match, startStr, endStr) => {
        const parseTime = (s: string) => {
            const parts = s.split(':').map(p => parseInt(p));
            if (parts.length === 2 && !isNaN(parts[1])) return parts[0] * 60 + parts[1];
            return !isNaN(parts[0]) ? parts[0] : 0;
        };
        const start = parseTime(startStr);
        const end = parseTime(endStr);
        const pad = (num: number) => num.toString().padStart(2, '0');
        const formatTime = (seconds: number) => `${pad(Math.floor(seconds / 60))}:${pad(seconds % 60)}`;
        return `[${formatTime(start)}–${formatTime(end)}]`;
    });
};

// Helper to build the final Grok prompt (TypeScript version of PromptBuilder.py)
const buildGrokPrompt = (scene: any): string => {
    const parts = ["6s:"];
    
    // 1. Description
    let desc = scene.grok_video_prompt?.full_prompt || scene.full_prompt || scene.image_to_video_prompt || scene.motion_description || scene.textToVideo || "";
    desc = formatTimeline(desc);
    parts.push(desc);

    // 2. Shot Type
    const camera = scene.camera_angle || scene.shot_type || scene.shotType || "";
    if (camera && !desc.toLowerCase().includes(camera.toLowerCase())) {
        parts.push(`Shot: ${camera.toLowerCase()}`);
    }

    // 3. Audio / Dialogue
    let audioBlock = "";
    const dialogue = scene.dialogue || "";
    const emotion = scene.emotion || scene.grok_video_prompt?.emotion || "neutrally";
    
    if (typeof dialogue === 'object' && dialogue !== null) {
        audioBlock = Object.entries(dialogue)
            .map(([char, text]) => `[${char}] (${emotion}): "${text}"`)
            .join(' ');
    } else if (dialogue) {
        audioBlock = `[Character] (${emotion}): "${dialogue}"`;
    }

    if (audioBlock) {
        parts.push(`AUDIO: ${audioBlock}`);
    }

    // 4. SFX
    const sfxList: string[] = [];
    if (Array.isArray(scene.sfx)) sfxList.push(...scene.sfx);
    if (scene.sound_effect) sfxList.push(scene.sound_effect);
    
    const uniqueSfx = Array.from(new Set(sfxList.filter(Boolean).map(s => s.trim())));
    if (uniqueSfx.length > 0) {
        parts.push(`SFX: ${uniqueSfx.join(', ')}.`);
    } else {
        parts.push(`SFX: .`); // Match user's request for trailing dot header
    }

    return parts.join(' ');
};

// Helper for parsing JSON script
const parseJsonScript = (jsonScript: string): ScriptBreakdown => {
    const parsed = JSON.parse(jsonScript);
    
    // Basic Validation
    if (!parsed.scenes || !Array.isArray(parsed.scenes)) {
        throw new Error("Invalid JSON: 'scenes' array is missing.");
    }

    // Map snake_case to camelCase and validate
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mappedScenes: any[] = parsed.scenes.map((s: any, idx: number) => ({
        index: idx,
        textToImage: s.text_to_image_prompt || s.static_image_prompt || s.text_to_image || s.image_prompt || s.textToImage || s.prompt || "",
        textToVideo: s.grok_video_prompt?.full_prompt || s.grokVideoPrompt?.fullPrompt || s.image_to_video_prompt || s.motion_description || s.text_to_video_prompt || s.video_prompt || s.motion_prompt || s.textToVideo || s.motion || "",
        characterPose: s.character_pose_prompt || s.character_pose || s.characterPose || s.pose || "",
        backgroundDesc: s.background_description || s.background_desc || s.backgroundDesc || s.background || "",
        shotType: s.camera_angle || s.camera_movement || s.shot_type || s.shotType || s.shot_type_prompt || "medium shot",
        imageUrl: s.imageUrl || s.image_url || null,
        videoUrl: s.videoUrl || s.video_url || null,
        // Map new structured fields
        grokVideoPrompt: {
            mainAction: s.grok_video_prompt?.main_action || s.grokVideoPrompt?.mainAction || s.main_action || "",
            cameraMovement: s.grok_video_prompt?.camera_movement || s.grokVideoPrompt?.cameraMovement || s.camera_movement,
            characterAnimation: s.grok_video_prompt?.character_animation || s.grokVideoPrompt?.characterAnimation || s.character_animation,
            emotion: s.grok_video_prompt?.emotion || s.grokVideoPrompt?.emotion || s.emotion,
            vfx: s.grok_video_prompt?.vfx || s.grokVideoPrompt?.vfx || s.vfx,
            lightingChanges: s.grok_video_prompt?.lighting_changes || s.grokVideoPrompt?.lightingChanges || s.lighting,
            fullPrompt: s.grok_video_prompt?.full_prompt || s.grokVideoPrompt?.fullPrompt || s.full_prompt,
        },
        sfx: s.sfx || (s.sound_effect ? [s.sound_effect] : []),
        musicNotes: s.music_notes || s.musicNotes || "",
        // Legacy fields
        dialogue: s.dialogue || "",
        // Ensure duration is present
        duration: s.duration_in_seconds || s.duration || 10,
        // Computed Preview Prompt
        formattedPrompt: buildGrokPrompt(s)
    }));

    // Map characters with aliases
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const mappedCharacters = (parsed.characters || []).map((c: any) => ({
        id: c.id || c.name || `char-${Math.random()}`,
        name: c.name,
        prompt: c.whisk_prompt || c.prompt || c.description || "",
        imageUrl: c.imageUrl || c.image_url,
        isLocked: c.isLocked || c.locked || false
    }));

    // Construct Breakdown
    return {
        title: parsed.title || "Imported Script",
        description: parsed.description || "",
        thumbnail_prompt: parsed.thumbnail_prompt || parsed.thumbnailPrompt || "",
        characters: mappedCharacters,
        scenes: mappedScenes
    };
};

export default function NewVideoPage() {
    const { currentStep, setStep, canProceed } = useProjectStore();
    const { isRunning } = useAutomationStore();

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">New Video</h1>
                <p className="text-muted-foreground">
                    Create a new AI-generated video in 5 steps
                </p>
            </div>

            {/* Step Indicator */}
            <div className="flex items-center justify-between">
                {STEPS.filter(step => !isRunning || step.number !== 4).map((step, index, filteredSteps) => (
                    <div key={step.number} className="flex items-center">
                        <button
                            onClick={() => step.number < currentStep && setStep(step.number as 1 | 2 | 3 | 4 | 5)}
                            className={`flex items-center gap-2 rounded-lg px-4 py-2 transition-colors ${currentStep === step.number
                                ? 'bg-primary text-primary-foreground'
                                : step.number < currentStep
                                    ? 'bg-muted hover:bg-muted/80 cursor-pointer'
                                    : 'bg-muted/50 text-muted-foreground cursor-not-allowed'
                                }`}
                            disabled={step.number > currentStep}
                        >
                            <step.icon className="h-4 w-4" />
                            <span className="hidden sm:inline">
                                {step.number === 3 && isRunning ? 'Scene Images/Videos' : step.title}
                            </span>
                            <span className="sm:hidden">{step.number}</span>
                        </button>
                        {index < filteredSteps.length - 1 && (
                            <ChevronRight className="h-4 w-4 mx-2 text-muted-foreground" />
                        )}
                    </div>
                ))}
            </div>

            {/* Step Content */}
            <Card>
                <CardContent className="pt-6">
                    {currentStep === 1 && <Step1Script />}
                    {currentStep === 2 && <Step2Characters />}
                    {currentStep === 3 && <Step3SceneImages />}
                    {currentStep === 4 && (!isRunning ? <Step4SceneVideos /> : <Step3SceneImages />)}
                    {currentStep === 5 && <Step5Final />}
                </CardContent>
            </Card>
        </div>
    );
}

// ============ STEP 1: Script Input ============
function Step1Script() {
    const {
        channelId, format, type, topic, narrative,
        setSettings, setTopic, setNarrative, setBreakdown, setStep
    } = useProjectStore();
    const { isRunning, progress, steps, currentAction, startAutomation } = useAutomationStore();

    const [scriptTab, setScriptTab] = useState<'ai' | 'manual' | 'json'>('manual');
    const [manualScript, setManualScript] = useState('');
    const [jsonScript, setJsonScript] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [autoUpload, setAutoUpload] = useState(true); // Default to True

    const { data: channelsData } = useQuery({
        queryKey: ['channels'],
        queryFn: () => db.get<{ channels: Channel[] }>('/channels'),
    });
    const channels = channelsData?.channels;

    // Default to "Wholesome paws" channel
    useEffect(() => {
        if (channels && !channelId) {
            const wholesomePaws = channels.find(ch => ch.name.toLowerCase().includes('wholesome paws'));
            if (wholesomePaws) {
                setSettings({ channelId: wholesomePaws.nicheId, format, type });
            }
        }
    }, [channels, channelId, setSettings, format, type]);

    // Auto-scroll when script is pasted
    useEffect(() => {
        if (scriptTab === 'manual' && manualScript.length > 50) {
            // Use a small timeout to let the DOM update
            setTimeout(() => {
                window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
            }, 100);
        }
    }, [manualScript, scriptTab]);

    const handleGenerateAI = async () => {
        if (!channelId || !topic) {
            toast.error('Please select a channel and enter a topic');
            return;
        }

        setIsGenerating(true);
        try {
            // Step 1: Generate narrative
            const narrativeResult = await api.post<{ narrative: string }>('/scripts/generate-story', {
                topic,
                niche_id: channelId,
                format,
                type,
            });
            setNarrative(narrativeResult.narrative);

            // Step 2: Generate breakdown
            const breakdown = await api.post<ScriptBreakdown>('/scripts/generate-breakdown', {
                story_narrative: narrativeResult.narrative,
                niche_id: channelId,
                scene_count: format === 'short' ? 8 : 12,
            });
            setBreakdown(breakdown);

            toast.success('Script generated successfully!');
            setStep(2);
        } catch (error) {
            toast.error(`Failed to generate script: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleManualContinue = async () => {
        if (!channelId || !manualScript) {
            toast.error('Please select a channel and paste your script');
            return;
        }

        setIsGenerating(true);
        try {
            const breakdown = await api.post<ScriptBreakdown>('/scripts/generate-breakdown', {
                story_narrative: manualScript,
                niche_id: channelId,
                scene_count: format === 'short' ? 8 : 12,
                video_length: format,  // 'short' or 'long'
                video_type: type,      // 'story' or 'documentary'
            });
            setNarrative(manualScript);
            setBreakdown(breakdown);

            toast.success('Script parsed successfully!');
            setStep(2);
        } catch (error) {
            toast.error(`Failed to parse script: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setIsGenerating(false);
        }
    };

    const handleOneClickAutomation = async () => {
        if (!channelId || !manualScript) {
            toast.error('Please select a channel and paste your script');
            return;
        }

        const result = await startAutomation(manualScript, channelId, format, autoUpload);
        if (result) {
            toast.success('Video generation complete!');
        }
    };

    const handleOneClickNoYouTube = async () => {
        if (!channelId || !manualScript) {
            toast.error('Please select a channel and paste your script');
            return;
        }

        const result = await startAutomation(manualScript, channelId, format, false);
        if (result) {
            toast.success('Video generation complete (without YouTube upload)!');
        }
    };

    const handleJsonAutomation = async () => {
        if (!channelId || !jsonScript) {
             toast.error('Please select a channel and paste your JSON script');
             return;
        }

        try {
             const breakdown = parseJsonScript(jsonScript);
             // Start automation with prepared breakdown (bypassing backend parsing)
             const result = await startAutomation(jsonScript, channelId, format, autoUpload, breakdown);
             if (result) {
                 toast.success('Video generation started from JSON!');
             }

        } catch (e) {
             toast.error(`Invalid JSON: ${e instanceof Error ? e.message : "Parse error"}`);
        }
    };

    const handleJsonContinue = () => {
        try {
            if (!jsonScript) return;
            // Use helper
            const breakdown = parseJsonScript(jsonScript);
            
            setBreakdown(breakdown);
            toast.success("JSON Script parsed successfully!");
            setStep(2);

        } catch (e) {
            toast.error(`Invalid JSON: ${e instanceof Error ? e.message : "Parse error"}`);
        }
    };

    return (
        <div className="space-y-6">
            {/* Channel Selection */}
            <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label>Channel</Label>
                    <Select value={channelId} onValueChange={(v) => setSettings({ channelId: v, format, type })}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select a channel" />
                        </SelectTrigger>
                        <SelectContent>
                            {channels?.map((ch) => (
                                <SelectItem key={ch.id} value={ch.nicheId}>
                                    {ch.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Format Selection */}
            <div className="grid gap-6 sm:grid-cols-2">
                <div className="space-y-3">
                    <Label>Format</Label>
                    <RadioGroup
                        value={format}
                        onValueChange={(v) => setSettings({ channelId, format: v as 'short' | 'long', type })}
                        className="flex gap-4"
                    >
                        <div className="flex items-center space-x-2">
                            <RadioGroupItem value="short" id="short" />
                            <Label htmlFor="short">Shorts (9:16)</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <RadioGroupItem value="long" id="long" />
                            <Label htmlFor="long">Long (16:9)</Label>
                        </div>
                    </RadioGroup>
                </div>

                <div className="space-y-3">
                    <Label>Type</Label>
                    <RadioGroup
                        value={type}
                        onValueChange={(v) => setSettings({ channelId, format, type: v as 'story' | 'documentary' })}
                        className="flex gap-4"
                    >
                        <div className="flex items-center space-x-2">
                            <RadioGroupItem value="story" id="story" />
                            <Label htmlFor="story">Story</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                            <RadioGroupItem value="documentary" id="documentary" />
                            <Label htmlFor="documentary">Documentary</Label>
                        </div>
                    </RadioGroup>
                </div>
            </div>

            <Separator />

            {/* Script Tabs */}
            <Tabs value={scriptTab} onValueChange={(v) => setScriptTab(v as 'ai' | 'manual' | 'json')}>
                <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="manual">Manual Script</TabsTrigger>
                    <TabsTrigger value="ai">AI Script</TabsTrigger>
                    <TabsTrigger value="json">JSON Script</TabsTrigger>
                </TabsList>

                <TabsContent value="manual" className="space-y-4 mt-4">
                    <div className="space-y-2">
                        <Label>Paste your pre-formatted script</Label>
                        <Textarea
                            value={manualScript}
                            onChange={(e) => setManualScript(e.target.value)}
                            placeholder={`CHARACTER MASTER PROMPTS:

[LUNA] - A small calico kitten with bright green eyes...

SCENE 1:
Text-to-Image: Close-up of Luna looking up...
Text-to-Video: Luna slowly tilts her head...
Dialogue: "Where am I?"`}
                            rows={10}
                        />
                    </div>
                    <div className="flex gap-4">
                        <Button onClick={handleManualContinue} disabled={isGenerating || !channelId || !manualScript}>
                            {isGenerating ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <ChevronRight className="mr-2 h-4 w-4" />
                            )}
                            Continue Manually
                        </Button>
                        <Button
                            variant="secondary"
                            onClick={handleOneClickAutomation}
                            disabled={isRunning || !channelId || !manualScript}
                        >
                            {isRunning ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <Rocket className="mr-2 h-4 w-4" />
                            )}
                            1-Click Automation
                        </Button>
                        <Button
                            variant="outline"
                            onClick={handleOneClickNoYouTube}
                            disabled={isRunning || !channelId || !manualScript}
                        >
                            {isRunning ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <Film className="mr-2 h-4 w-4" />
                            )}
                            1-Click (No YouTube)
                        </Button>
                    </div>
                </TabsContent>

                <TabsContent value="ai" className="space-y-4 mt-4">
                    <div className="space-y-2">
                        <Label>Enter your story idea or topic</Label>
                        <Textarea
                            value={topic}
                            onChange={(e) => setTopic(e.target.value)}
                            placeholder="A heartwarming story about a brave little kitten who helps lost animals find their way home in a magical forest..."
                            rows={4}
                        />
                    </div>
                    <Button onClick={handleGenerateAI} disabled={isGenerating || !channelId || !topic}>
                        {isGenerating ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <Wand2 className="mr-2 h-4 w-4" />
                        )}
                        Generate Script
                    </Button>
                </TabsContent>

                <TabsContent value="json" className="space-y-4 mt-4">
                    <div className="space-y-2">
                        <Label>Paste Valid JSON Script</Label>
                        <Textarea
                            value={jsonScript}
                            onChange={(e) => setJsonScript(e.target.value)}
                            placeholder='{ "title": "My Video", "scenes": [ ... ] }'
                            rows={15}
                            className="font-mono text-xs"
                        />
                    </div>
                    <div className="flex gap-4">
                        <Button onClick={handleJsonContinue} disabled={!jsonScript}>
                            <FileJson className="mr-2 h-4 w-4" />
                            Parse & Continue
                        </Button>
                        <Button 
                            variant="secondary"
                            onClick={handleJsonAutomation}
                            disabled={!jsonScript || !channelId || isRunning}
                        >
                            {isRunning ? (
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                                <Rocket className="mr-2 h-4 w-4" />
                            )}
                            1-Click Automation
                        </Button>
                    </div>
                </TabsContent>
            </Tabs>

            {/* Automation Options */}
            <div className="flex items-center space-x-2 pt-2">
                <input
                    type="checkbox"
                    id="autoUpload"
                    checked={autoUpload}
                    onChange={(e) => setAutoUpload(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                />
                <Label htmlFor="autoUpload" className="text-sm font-medium cursor-pointer">
                    Auto-upload to YouTube (Unlisted)
                </Label>
                <Badge variant="outline" className="text-[10px] ml-2">PRO</Badge>
            </div>

            {/* Automation Progress */}
            {isRunning && (
                <AutomationProgress
                    progress={progress}
                    steps={steps}
                    currentAction={currentAction}
                />
            )}
        </div>
    );
}

// ============ STEP 2: Characters ============
function Step2Characters() {
    const { characters, updateCharacter, setStep, canProceed, channelId, format } = useProjectStore();
    const [generatingIndex, setGeneratingIndex] = useState<number | null>(null);

    const handleGenerateImage = async (index: number) => {
        const character = characters[index];
        setGeneratingIndex(index);

        try {
            const result = await api.post<{ image_url: string }>('/characters/generate-image', {
                character_name: character.name,
                prompt: character.prompt,
                niche_id: channelId,  // Include the channel/niche ID
                is_shorts: format === 'short', // Fix: Pass correct format
            });
            updateCharacter(index, { imageUrl: result.image_url });
            toast.success(`${character.name} image generated!`);
        } catch (error) {
            toast.error(`Failed to generate image: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setGeneratingIndex(null);
        }
    };

    const allLocked = characters.every((c) => c.isLocked && c.imageUrl);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">Master Cast</h2>
                    <p className="text-sm text-muted-foreground">
                        Generate and lock character images for consistency
                    </p>
                </div>
            </div>

            <div className="grid gap-4">
                {characters.map((character, index) => (
                    <Card key={character.name}>
                        <CardContent className="flex gap-4 p-4">
                            {/* Image Preview */}
                            <div className="w-32 h-32 rounded-lg border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0">
                                {character.imageUrl ? (
                                    <img
                                        src={character.imageUrl}
                                        alt={character.name}
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <ImageIcon className="h-8 w-8 text-muted-foreground" />
                                )}
                            </div>

                            {/* Character Info */}
                            <div className="flex-1 space-y-2">
                                <div className="flex items-center justify-between">
                                    <h3 className="font-semibold">{character.name}</h3>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            size="sm"
                                            variant={character.isLocked ? 'secondary' : 'outline'}
                                            onClick={() => updateCharacter(index, { isLocked: !character.isLocked })}
                                            disabled={!character.imageUrl}
                                        >
                                            {character.isLocked ? (
                                                <Lock className="h-4 w-4 mr-1" />
                                            ) : (
                                                <Unlock className="h-4 w-4 mr-1" />
                                            )}
                                            {character.isLocked ? 'Locked' : 'Unlocked'}
                                        </Button>
                                    </div>
                                </div>
                                <p className="text-sm text-muted-foreground line-clamp-3">
                                    {character.prompt}
                                </p>
                                <Button
                                    size="sm"
                                    onClick={() => handleGenerateImage(index)}
                                    disabled={generatingIndex !== null || character.isLocked}
                                >
                                    {generatingIndex === index ? (
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    ) : (
                                        <Wand2 className="h-4 w-4 mr-2" />
                                    )}
                                    Generate Image
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Navigation */}
            <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(1)}>
                    <ChevronLeft className="h-4 w-4 mr-2" />
                    Back
                </Button>
                <Button onClick={() => setStep(3)} disabled={!allLocked}>
                    Next: Scene Images
                    <ChevronRight className="h-4 w-4 ml-2" />
                </Button>
            </div>
        </div>
    );
}

// ============ STEP 3: Scene Images ============
function Step3SceneImages() {
    const { 
        scenes, characters, updateScene, setStep, 
        channelId, format, thumbnailUrl, thumbnailPrompt, setThumbnailUrl 
    } = useProjectStore();
    const { isRunning } = useAutomationStore();
    const [generatingIndex, setGeneratingIndex] = useState<number | null>(null);
    const [generatingAll, setGeneratingAll] = useState(false);

    const handleGenerateImage = async (index: number) => {
        // ... (rest of handleGenerateImage logic remains same)
        const scene = scenes[index];
        setGeneratingIndex(index);

        try {
            const result = await api.post<{ imageUrl: string }>('/scenes/generate-image', {
                prompt: scene.textToImage,
                character_images: characters.map((c) => ({ name: c.name, imageUrl: c.imageUrl })),
                niche_id: channelId,
                scene_index: index,
                is_shorts: format === 'short',
            });
            updateScene(index, { imageUrl: result.imageUrl });
            toast.success(`Scene ${index + 1} image generated!`);
        } catch (error) {
            toast.error(`Failed to generate scene image: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setGeneratingIndex(null);
        }
    };

    const handleGenerateAll = async () => {
        setGeneratingAll(true);
        try {
            const scenesToGenerate = scenes
                .filter(s => !s.imageUrl)
                .map(s => ({ index: s.index, prompt: s.textToImage }));

            const state = useProjectStore.getState();
            const threadThumbPrompt = state.thumbnailPrompt;
            const hasThumbnail = !!state.thumbnailUrl;

            // If nothing to generate, but we have a thumbnail prompt and no thumbnail, we should just generate the thumbnail
            const shouldGenerateThumbnail = !!threadThumbPrompt && !hasThumbnail;

            if (scenesToGenerate.length === 0 && !shouldGenerateThumbnail) {
                toast.info("All scenes already have images!");
                setGeneratingAll(false);
                return;
            }

            toast.loading(`Starting batch generation...`);

            // Use fetch for streaming response
            const response = await fetch('http://localhost:8000/scenes/generate-images-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    niche_id: channelId,
                    scenes: scenesToGenerate,
                    character_images: characters.map((c) => ({ name: c.name, imageUrl: c.imageUrl })),
                    video_type: format === 'short' ? 'shorts' : 'story',
                    thumbnail_prompt: shouldGenerateThumbnail ? threadThumbPrompt : undefined
                })
            });

            if (!response.ok || !response.body) {
                throw new Error('Failed to start stream');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let successCount = 0;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                
                // Process all complete lines
                buffer = lines.pop() || ''; 

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        
                        if (data.type === 'thumbnail') {
                            if (data.imageUrl) {
                                setThumbnailUrl(data.imageUrl);
                                toast.success("Thumbnail generated!");
                            } else if (data.error) {
                                console.error("Thumbnail failed:", data.error);
                            }
                        } else {
                            // Scene update
                            if (data.imageUrl) {
                                updateScene(data.index, { imageUrl: data.imageUrl });
                                successCount++;
                            } else if (data.error) {
                                console.error(`Scene ${data.index + 1} failed: ${data.error}`);
                            }
                        }
                    } catch (e) {
                        console.error('Error parsing JSON line:', e);
                    }
                }
            }

            toast.dismiss();
            toast.success(`Batch generation complete!`);

        } catch (error) {
            toast.error(`Batch generation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setGeneratingAll(false);
        }
    };

    const allImagesGenerated = scenes.every((s) => s.imageUrl);
    const allVideosGenerated = scenes.every((s) => s.videoUrl);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">
                        {isRunning ? 'Scene Images & Videos' : 'Scene Images'}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        {isRunning
                            ? 'Monitor the automated generation of images and videos'
                            : 'Generate images for each scene using Whisk'}
                    </p>
                </div>
                {!isRunning && (
                    <Button onClick={handleGenerateAll} disabled={generatingAll || allImagesGenerated}>
                        {generatingAll ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <ImagePlus className="h-4 w-4 mr-2" />
                        )}
                        Generate All Images
                    </Button>
                )}
            </div>

            {/* Character Reference */}
            <div className="flex gap-2 overflow-x-auto pb-2">
                <span className="text-sm text-muted-foreground self-center">Characters:</span>
                {characters.map((c) => (
                    <div key={c.name} className="flex-shrink-0">
                        {c.imageUrl && (
                            <img
                                src={c.imageUrl}
                                alt={c.name}
                                className="w-10 h-10 rounded-full object-cover border"
                                title={c.name}
                            />
                        )}
                    </div>
                ))}
            </div>

            <div className="grid gap-4">
                {scenes.map((scene, index) => (
                    <Card key={index} className="overflow-hidden">
                        <CardContent className="p-0">
                            <div className="flex flex-col">
                                {/* Row 1: Image */}
                                <div className="flex gap-4 p-4 border-b bg-card/50">
                                    <div className="w-40 h-40 rounded-lg border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0 relative group">
                                        {scene.imageUrl ? (
                                            <img src={scene.imageUrl} alt={`Scene ${index + 1}`} className="w-full h-full object-cover" />
                                        ) : (
                                            <div className="flex flex-col items-center gap-2">
                                                <ImageIcon className="h-10 w-10 text-muted-foreground" />
                                                <span className="text-[10px] text-muted-foreground uppercase font-bold">Waiting for Image</span>
                                            </div>
                                        )}
                                        {scene.imageUrl && (
                                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                                <Badge variant="secondary">Scene {index + 1} Image</Badge>
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex-1 space-y-2 py-2">
                                        <div className="flex items-center gap-2">
                                            <h3 className="font-bold text-lg">Scene {index + 1}</h3>
                                            <Badge variant="outline" className="text-[10px] h-5">IMAGE PHASE</Badge>
                                        </div>
                                        <div className="space-y-1">
                                            <p className="text-[10px] uppercase font-bold text-muted-foreground/70">Text-to-Image Prompt</p>
                                            <p className="text-sm leading-relaxed">{scene.textToImage}</p>
                                        </div>
                                        {!isRunning && (
                                            <Button
                                                size="sm"
                                                onClick={() => handleGenerateImage(index)}
                                                disabled={generatingIndex !== null || generatingAll}
                                                className="mt-2"
                                            >
                                                {generatingIndex === index ? (
                                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                ) : (
                                                    <Wand2 className="h-4 w-4 mr-2" />
                                                )}
                                                Regenerate Image
                                            </Button>
                                        )}
                                    </div>
                                </div>

                                {/* Row 2: Video (Only if running or has video) */}
                                {(isRunning || scene.videoUrl) && (
                                    <div className="flex gap-4 p-4 bg-muted/20">
                                        <div className="w-40 h-40 rounded-lg border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0 relative group">
                                            {scene.videoUrl ? (
                                                <video src={scene.videoUrl} className="w-full h-full object-cover" controls />
                                            ) : (
                                                <div className="flex flex-col items-center gap-2">
                                                    <Loader2 className={`h-10 w-10 text-muted-foreground ${scene.imageUrl && isRunning ? 'animate-spin' : ''}`} />
                                                    <span className="text-[10px] text-muted-foreground uppercase font-bold text-center px-2">
                                                        {scene.imageUrl ? 'Generating Video...' : 'Waiting for Image'}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex-1 space-y-2 py-2">
                                            <div className="flex items-center gap-2">
                                                <Badge variant="secondary" className="text-[10px] h-5 bg-blue-500/20 text-blue-400 border-blue-500/30">VIDEO PHASE</Badge>
                                                {scene.shotType && (
                                                    <Badge variant="outline" className="text-[10px] h-5 uppercase">{scene.shotType}</Badge>
                                                )}
                                            </div>
                                            <div className="space-y-1">
                                                <p className="text-[10px] uppercase font-bold text-muted-foreground/70">Image-to-Video Description</p>
                                                <p className="text-sm leading-relaxed italic text-muted-foreground">
                                                    {scene.textToVideo || "Waiting for character-driven motion analysis..."}
                                                </p>
                                            </div>
                                            {scene.dialogue && (
                                                <div className="pt-1">
                                                    <p className="text-[10px] uppercase font-bold text-muted-foreground/70 mb-1">🎤 Voiceover/Dialogue</p>
                                                    <div className="bg-background/50 border rounded px-3 py-1.5 text-sm">
                                                        {typeof scene.dialogue === 'object' 
                                                            ? Object.entries(scene.dialogue).map(([char, text]) => `${char}: "${text}"`).join(' ')
                                                            : scene.dialogue}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* YouTube Thumbnail Card */}
            <div className="mt-8">
                <Card className="border-dashed border-2 bg-card/30">
                    <CardHeader className="pb-2">
                        <div className="flex items-center gap-2">
                            <span className="p-1.5 bg-red-500/10 text-red-500 rounded">
                                <Youtube className="h-4 w-4" />
                            </span>
                            <CardTitle className="text-sm font-bold uppercase tracking-wider">YouTube Viral Thumbnail</CardTitle>
                            <Badge variant="secondary" className="ml-auto text-[10px]">THUMBNAIL PHASE</Badge>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="flex gap-4">
                            <div className="w-40 h-40 rounded-lg border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0 relative group">
                                {thumbnailUrl ? (
                                    <img src={thumbnailUrl} alt="Viral Thumbnail" className="w-full h-full object-cover" />
                                ) : (
                                    <div className="flex flex-col items-center gap-2">
                                        <ImageIcon className="h-10 w-10 text-muted-foreground" />
                                        <span className="text-[10px] text-muted-foreground uppercase font-bold">
                                            {generatingAll ? 'Generating...' : 'Waiting for Batch'}
                                        </span>
                                    </div>
                                )}
                            </div>
                            <div className="flex-1 space-y-2 py-2">
                                <div className="space-y-1">
                                    <p className="text-[10px] uppercase font-bold text-muted-foreground/70">Viral Thumbnail Prompt</p>
                                    <p className="text-sm border rounded-md p-3 bg-background/50 italic leading-relaxed">
                                        {thumbnailPrompt || "Generating viral prompt from script context..."}
                                    </p>
                                </div>
                                <p className="text-[10px] text-muted-foreground italic">
                                    * This thumbnail is generated once the batch generation starts.
                                </p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(isRunning ? 2 : 2)}>
                    <ChevronLeft className="h-4 w-4 mr-2" />
                    Back
                </Button>
                <Button
                    onClick={() => setStep(5)}
                    disabled={isRunning ? (!allImagesGenerated || !allVideosGenerated) : !allImagesGenerated}
                >
                    {isRunning ? 'Next: Final Render' : 'Next: Scene Videos'}
                    <ChevronRight className="h-4 w-4 ml-2" />
                </Button>
            </div>
        </div>
    );
}

// ============ STEP 4: Scene Videos ============
function Step4SceneVideos() {
    const { scenes, updateScene, setStep, channelId, format } = useProjectStore();
    const [generatingIndex, setGeneratingIndex] = useState<number | null>(null);
    const [generatingAll, setGeneratingAll] = useState(false);

    const handleGenerateVideo = async (index: number, retryCount = 0): Promise<boolean> => {
        const MAX_RETRIES = 3;
        const scene = scenes[index];

        if (!scene.imageUrl) {
            toast.error(`Scene ${index + 1} has no image URL. Please generate the image in Step 3 first.`);
            return false;
        }

        setGeneratingIndex(index);

        try {
            const result = await api.post<{ videoUrl: string, formattedPrompt: string }>('/scenes/generate-video', {
                scene_index: index,
                image_url: scene.imageUrl,
                prompt: scene.textToVideo,
                dialogue: scene.dialogue,
                camera_angle: scene.shotType,
                niche_id: channelId,
                is_shorts: format === 'short',
            });

            // Validate the response has a proper video URL
            if (!result.videoUrl || result.videoUrl.trim() === '') {
                throw new Error('Empty video URL returned');
            }

            updateScene(index, { 
                videoUrl: result.videoUrl,
                isValidVideo: true,
                formattedPrompt: result.formattedPrompt 
            });
            toast.success(`Scene ${index + 1} video generated!`);
            return true;
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Unknown error';

            if (retryCount < MAX_RETRIES) {
                const delay = Math.pow(2, retryCount) * 1000; // Exponential backoff: 1s, 2s, 4s
                toast.warning(`Scene ${index + 1} failed, retrying in ${delay / 1000}s... (Attempt ${retryCount + 1}/${MAX_RETRIES})`);
                await new Promise(resolve => setTimeout(resolve, delay));
                setGeneratingIndex(null);
                return handleGenerateVideo(index, retryCount + 1);
            }

            toast.error(`Failed to generate video for Scene ${index + 1} after ${MAX_RETRIES} attempts: ${errorMsg}`);
            return false;
        } finally {
            setGeneratingIndex(null);
        }
    };

    const handleGenerateAll = async () => {
        setGeneratingAll(true);
        
        const verifyAllVideos = async (currentScenes: typeof scenes) => {
            const invalidIndices: number[] = [];
            for (let i = 0; i < currentScenes.length; i++) {
                const scene = currentScenes[i];
                if (!scene.videoUrl) {
                    invalidIndices.push(i);
                    updateScene(i, { isValidVideo: false });
                    continue;
                }
                try {
                    const verification = await api.post<{ valid: boolean }>('/videos/verify', {
                        video_url: scene.videoUrl
                    });
                    updateScene(i, { isValidVideo: verification.valid });
                    if (!verification.valid) invalidIndices.push(i);
                } catch (e) {
                    console.error(`Verification failed for scene ${i + 1}`, e);
                    updateScene(i, { isValidVideo: false });
                    invalidIndices.push(i);
                }
            }
            return invalidIndices;
        };

        // Pass 1: Initial generation for missing videos
        for (let i = 0; i < scenes.length; i++) {
            if (!scenes[i].videoUrl) {
                await handleGenerateVideo(i);
            }
        }

        // Pass 2: Identification & Retry
        let invalidIndices = await verifyAllVideos(useProjectStore.getState().scenes);
        if (invalidIndices.length > 0) {
            toast.warning(`${invalidIndices.length} videos invalid or missing. Retrying...`);
            for (const idx of invalidIndices) {
                await handleGenerateVideo(idx);
            }
        }

        // Pass 3: Final Verification (Non-optional)
        const finalInvalid = await verifyAllVideos(useProjectStore.getState().scenes);

        if (finalInvalid.length === 0) {
            toast.success('All videos verified successfully! Moving to final tab...');
            setTimeout(() => setStep(5), 1500); 
        } else {
            toast.error(`${finalInvalid.length} videos are still invalid. Please check scenes: ${finalInvalid.map(i => i + 1).join(', ')}`);
        }

        setGeneratingAll(false);
    };

    const allValidated = scenes.every((s) => s.videoUrl && s.isValidVideo);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">Scene Videos</h2>
                    <p className="text-sm text-muted-foreground">
                        Animate scene images using Grok
                    </p>
                </div>
                <Button onClick={handleGenerateAll} disabled={generatingAll || allValidated}>
                    {generatingAll ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                        <Film className="h-4 w-4 mr-2" />
                    )}
                    {allValidated ? 'All Videos Verified' : 'Generate/Verify All Videos'}
                </Button>
            </div>

            <div className="grid gap-4">
                {scenes.map((scene, index) => (
                    <Card key={index}>
                        <CardContent className="flex gap-4 p-4">
                            {/* Image */}
                            <div className="w-32 h-32 rounded-lg border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0">
                                {scene.imageUrl && (
                                    <img src={scene.imageUrl} alt={`Scene ${index + 1}`} className="w-full h-full object-cover" />
                                )}
                            </div>
                            {/* Video */}
                            <div className={`w-32 h-32 rounded-lg border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0 relative ${scene.videoUrl && scene.isValidVideo === false ? 'border-red-500' : ''}`}>
                                {scene.videoUrl ? (
                                    <video src={scene.videoUrl} className="w-full h-full object-cover" controls />
                                ) : (
                                    <Play className="h-8 w-8 text-muted-foreground" />
                                )}
                                {scene.videoUrl && scene.isValidVideo === false && (
                                    <div className="absolute top-1 right-1 bg-red-500 rounded-full p-1" title="Corrupt or invalid video detected">
                                        <AlertCircle className="h-3 w-3 text-white" />
                                    </div>
                                )}
                            </div>
                            <div className="flex-1 space-y-2">
                                <div className="flex items-center gap-2">
                                    <h3 className="font-semibold">Scene {index + 1}{scene.title && `: ${scene.title}`}</h3>
                                    {scene.shotType && (
                                        <span className="text-xs bg-muted px-2 py-0.5 rounded">{scene.shotType}</span>
                                    )}
                                </div>
                                <p className="text-sm text-muted-foreground line-clamp-2">
                                    <strong>Motion:</strong> {scene.textToVideo}
                                </p>
                                {scene.dialogue && (
                                    <p className="text-sm text-muted-foreground">
                                        <strong>🎤 Dialogue:</strong> {typeof scene.dialogue === 'object' 
                                            ? Object.entries(scene.dialogue).map(([char, text]) => `${char}: "${text}"`).join(' ')
                                            : scene.dialogue}
                                    </p>
                                )}
                                {(scene.formattedPrompt || buildGrokPrompt(scene)) && (
                                    <div className="mt-2 p-2 bg-blue-500/10 border border-blue-500/20 rounded-md">
                                        <p className="text-[10px] uppercase font-bold text-blue-400 mb-1">🎬 Final Grok Imagine Prompt</p>
                                        <p className="text-xs text-blue-100/80 italic font-mono leading-relaxed">
                                            {scene.formattedPrompt || buildGrokPrompt(scene)}
                                        </p>
                                    </div>
                                )}
                                <Button
                                    size="sm"
                                    onClick={() => handleGenerateVideo(index)}
                                    disabled={generatingIndex !== null || generatingAll}
                                >
                                    {generatingIndex === index ? (
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    ) : (
                                        <Film className="h-4 w-4 mr-2" />
                                    )}
                                    Generate Video
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(3)}>
                    <ChevronLeft className="h-4 w-4 mr-2" />
                    Back
                </Button>
                <Button onClick={() => setStep(5)} disabled={!allValidated}>
                    Next: Final Video
                    <ChevronRight className="h-4 w-4 ml-2" />
                </Button>
            </div>
        </div>
    );
}

// ============ STEP 5: Final Render ============
// ============ STEP 5: Final Render ============
function Step5Final() {
    const { 
        scenes, channelId, finalVideoUrl, setFinalVideoUrl, 
        thumbnailUrl, thumbnailPrompt, setStep, reset, format, breakdown 
    } = useProjectStore();
    const [isStitching, setIsStitching] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [musicOption, setMusicOption] = useState('upbeat');
    const [generateMetadata, setGenerateMetadata] = useState(true);

    const handleStitch = async () => {
        setIsStitching(true);
        try {
            const result = await api.post<{ status: string; final_video_url: string; clips_stitched: number }>('/videos/stitch', {
                video_urls: scenes.map((s) => s.videoUrl).filter(url => !!url),
                niche_id: channelId,
                title: breakdown?.title || 'Stitched Video',
                music: musicOption,
                is_shorts: format === 'short',
            });
            setFinalVideoUrl(result.final_video_url);
            toast.success('Video stitched successfully!');
        } catch (error) {
            toast.error(`Failed to stitch video: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setIsStitching(false);
        }
    };

    const handleUpload = async () => {
        setIsUploading(true);
        try {
            // Prepare script context for metadata generation
            const scriptContext = breakdown?.description 
                ? `${breakdown.title}\n\n${breakdown.description}` 
                : breakdown?.scenes.map(s => s.dialogue).join("\n") || "";

            await api.post('/upload/youtube', {
                video_url: finalVideoUrl,
                niche_id: channelId,
                title: breakdown?.title || 'AI Generated Video',
                description: breakdown?.description || 'Created with AI Video Factory',
                thumbnail_url: thumbnailUrl,
                generate_metadata: generateMetadata,
                script_context: scriptContext
            });
            toast.success('Video uploaded to YouTube!');
        } catch (error) {
            toast.error(`Failed to upload: ${error instanceof Error ? error.message : 'Unknown error'}`);
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-semibold">Final Video</h2>
                <p className="text-sm text-muted-foreground">
                    Stitch all scenes and upload to platforms
                </p>
            </div>

            {/* Options */}
            <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                    <Label>Background Music</Label>
                    <Select value={musicOption} onValueChange={setMusicOption}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="upbeat">Upbeat / Happy</SelectItem>
                            <SelectItem value="epic">Epic / Cinematic</SelectItem>
                            <SelectItem value="calm">Calm / Ambient</SelectItem>
                            <SelectItem value="horror">Horror / Suspense</SelectItem>
                            <SelectItem value="dramatic">Dramatic / Intense</SelectItem>
                            <SelectItem value="hiphop">Hip-Hop / Urban</SelectItem>
                            <SelectItem value="jazz">Jazz / Lounge</SelectItem>
                            <SelectItem value="piano">Piano / Romantic</SelectItem>
                            <SelectItem value="rock">Rock / Energetic</SelectItem>
                            <SelectItem value="auto">Auto-Select (AI)</SelectItem>
                            <SelectItem value="none">No Music</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Stitch Button */}
            <Button onClick={handleStitch} disabled={isStitching || !!finalVideoUrl} className="w-full">
                {isStitching ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                    <Film className="h-4 w-4 mr-2" />
                )}
                Stitch All Videos
            </Button>

            {/* Video Preview */}
            {finalVideoUrl && (
                <div className="space-y-6">
                    <div className="grid gap-6 md:grid-cols-2">
                        {/* Video */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Final Video</CardTitle>
                            </CardHeader>
                            <CardContent className="p-4">
                                <video src={finalVideoUrl} controls className="w-full rounded-lg" />
                            </CardContent>
                        </Card>

                        {/* Thumbnail */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">YouTube Thumbnail</CardTitle>
                            </CardHeader>
                            <CardContent className="p-4 flex flex-col gap-4">
                                <div className="aspect-video w-full bg-muted rounded-lg overflow-hidden flex items-center justify-center relative">
                                    {thumbnailUrl ? (
                                        <img src={thumbnailUrl} alt="Thumbnail" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="text-center p-4">
                                            <ImageIcon className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                                            <p className="text-sm text-muted-foreground">
                                                {thumbnailPrompt ? "Thumbnail generating..." : "No thumbnail available"}
                                            </p>
                                        </div>
                                    )}
                                </div>
                                {thumbnailUrl && (
                                    <div className="flex items-center space-x-2">
                                        <input 
                                            type="checkbox" 
                                            id="genMeta" 
                                            checked={generateMetadata}
                                            onChange={(e) => setGenerateMetadata(e.target.checked)}
                                            className="h-4 w-4 rounded border-gray-300"
                                        />
                                        <Label htmlFor="genMeta" className="text-sm cursor-pointer">
                                            Auto-generate Viral Title/Desc/Tags
                                        </Label>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Upload Buttons */}
                    <div className="flex gap-4">
                        <Button onClick={handleUpload} disabled={isUploading}>
                            {isUploading ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            ) : (
                                <Upload className="h-4 w-4 mr-2" />
                            )}
                            Upload to YouTube
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => {
                                reset();
                                toast.success('Project reset. Ready for a new video!');
                            }}
                        >
                            Start New Project
                        </Button>
                    </div>
                </div>
            )}

            <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(4)}>
                    <ChevronLeft className="h-4 w-4 mr-2" />
                    Back
                </Button>
            </div>
        </div>
    );
}

// ============ Automation Progress Component ============
function AutomationProgress({
    progress,
    steps,
    currentAction
}: {
    progress: number;
    steps: { name: string; status: string; errorMessage?: string }[];
    currentAction: string;
}) {
    return (
        <Card className="mt-6">
            <CardHeader>
                <CardTitle className="text-lg">1-Click Automation Progress</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <Progress value={progress} />
                <div className="space-y-2">
                    {steps.map((step, index) => (
                        <div key={index} className="flex items-center gap-2 text-sm">
                            {step.status === 'done' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                            {step.status === 'running' && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
                            {step.status === 'pending' && <Clock className="h-4 w-4 text-muted-foreground" />}
                            {step.status === 'error' && <XCircle className="h-4 w-4 text-red-500" />}
                            <span className={step.status === 'pending' ? 'text-muted-foreground' : ''}>
                                {step.name}
                            </span>
                            {step.errorMessage && (
                                <span className="text-red-500">- {step.errorMessage}</span>
                            )}
                        </div>
                    ))}
                </div>
                {currentAction && (
                    <p className="text-sm text-muted-foreground">{currentAction}</p>
                )}
            </CardContent>
        </Card>
    );
}
