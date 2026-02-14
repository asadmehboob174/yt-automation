// TypeScript interfaces for the AI Video Factory

// ============ Channel Types ============
export interface Channel {
    id: string;
    nicheId: string;
    name: string;
    styleSuffix: string;
    voiceId: string;
    anchorImage?: string;
    bgMusic?: string;
    youtubeId?: string;
    defaultTags: string[];
    thumbnailStyle?: string;
    apiToken?: string;
}

export interface CreateChannelRequest {
    nicheId: string;
    name: string;
    styleSuffix: string;
    voiceId: string;
    defaultTags?: string[];
}

// ============ Character Types ============
export interface Character {
    id: string;
    channelId: string;
    name: string;
    prompt: string;
    imageUrl?: string;
    isLocked: boolean;
}

// ============ Scene Types ============
export interface Scene {
    index: number;
    title?: string;
    textToImage: string;
    textToVideo: string;
    textToVideoPrompt: string;   // grok_video_prompt.text_to_video_prompt (audio source)
    textToVideoUrl?: string;     // generated text-to-video clip URL
    dialogue?: string;
    shotType?: string;  // e.g., "Medium Shot", "Close-up"
    imageUrl?: string;
    videoUrl?: string;
    isValidVideo?: boolean;
    // New structured fields
    grokVideoPrompt?: {
        mainAction: string;
        cameraMovement?: string;
        characterAnimation?: string;
        emotion?: string;
        vfx?: string;
        lightingChanges?: string;
        fullPrompt?: string;
    };
    sfx?: string[];
    musicNotes?: string;
    formattedPrompt?: string;
}

// ============ Script Types ============
export interface ScriptBreakdown {
    title: string;
    description?: string;
    thumbnail_prompt?: string;
    characters: Character[];
    scenes: Scene[];
    youtube_upload?: any;
    final_assembly?: any;
}

export interface GenerateScriptRequest {
    topic: string;
    nicheId: string;
    sceneCount?: number;
    format: 'short' | 'long';
    type: 'story' | 'documentary';
}

export interface GenerateBreakdownRequest {
    storyNarrative: string;
    nicheId: string;
    sceneCount?: number;
}

// ============ Video Types ============
export interface Video {
    id: string;
    channelId: string;
    title: string;
    status: 'DRAFT' | 'PROCESSING' | 'RENDERED' | 'UPLOADED' | 'ERROR';
    script?: ScriptBreakdown;
    videoUrl?: string;
    youtubeUrl?: string;
    jobId?: string;
    createdAt: string;
}

// ============ Queue Types ============
export interface QueueItem {
    id: string;
    name: string;
    channelId: string;
    format: 'short' | 'long';
    type: 'story' | 'documentary';
    script: string;
    status: 'queued' | 'processing' | 'done' | 'error';
    platforms: string[];
    createdAt: string;
    errorMessage?: string;
}

// ============ Platform Types ============
export interface PlatformStatus {
    youtube: boolean;
    instagram: boolean;
    tiktok: boolean;
    facebook: boolean;
}

// ============ Automation Types ============
export type AutomationStepStatus = 'pending' | 'running' | 'done' | 'error';

export interface AutomationStep {
    name: string;
    status: AutomationStepStatus;
    progress?: string;
    errorMessage?: string;
}

// ============ API Response Types ============
export interface HealthResponse {
    status: string;
    database?: boolean;
    storage?: boolean;
    gemini?: boolean;
    huggingface?: boolean;
}

export interface StorageStats {
    totalSize: number;
    fileCount: number;
    bucketName: string;
}
