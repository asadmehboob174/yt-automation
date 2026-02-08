"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

// Types
export type VideoLength = "short" | "long";
export type VideoType = "story" | "documentary";

export interface MasterCharacter {
  id: string; // generated uuid
  name: string;
  prompt: string;
  imageUrl?: string;
  locked: boolean;
  isGenerating: boolean;
}

export interface SceneBreakdown {
  scene_number: number;
  scene_title: string;
  voiceover_text: string;
  character_pose_prompt: string;
  background_description: string;
  text_to_image_prompt: string;
  image_to_video_prompt: string;
  motion_description: string;
  duration_in_seconds: number;
  camera_angle: string;
  dialogue?: string;
  imageUrl?: string;
  videoUrl?: string;
  isGeneratingImage: boolean;
  isGeneratingVideo: boolean;
}

interface ProjectState {
  // Video settings
  videoLength: VideoLength;
  videoType: VideoType;
  setVideoLength: (length: VideoLength) => void;
  setVideoType: (type: VideoType) => void;
  
  // Story stage
  storyIdea: string;
  storyNarrative: string;
  setStoryIdea: (idea: string) => void;
  setStoryNarrative: (narrative: string) => void;
  
  // Characters
  masterCharacters: MasterCharacter[];
  setMasterCharacters: (chars: MasterCharacter[]) => void;
  updateCharacter: (id: string, updates: Partial<MasterCharacter>) => void;
  
  // Scenes
  sceneBreakdown: SceneBreakdown[];
  setSceneBreakdown: (scenes: SceneBreakdown[]) => void;
  updateScene: (index: number, updates: Partial<SceneBreakdown>) => void;
  
  // Progress
  currentStage: number; // 0=Settings, 1=Story, 2=Characters, 3=Scenes, 4=Animation
  setCurrentStage: (stage: number) => void;

  // Style
  styleReferenceUrl?: string;
  setStyleReferenceUrl: (url: string) => void;
  stylePrompt?: string;
  setStylePrompt: (prompt: string) => void;
  
  // Auto-Run
  isAutoRun: boolean;
  setIsAutoRun: (auto: boolean) => void;
}

const ProjectContext = createContext<ProjectState | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
  // Helper to load from storage safely
  const loadState = <T,>(key: string, defaultVal: T): T => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('projectState');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          return parsed[key] !== undefined ? parsed[key] : defaultVal;
        } catch (e) {
          console.error("Failed to parse project state", e);
        }
      }
    }
    return defaultVal;
  };

  const [videoLength, setVideoLength] = useState<VideoLength>(() => loadState('videoLength', "short"));
  const [videoType, setVideoType] = useState<VideoType>(() => loadState('videoType', "story"));
  
  const [storyIdea, setStoryIdea] = useState(() => loadState('storyIdea', ""));
  const [storyNarrative, setStoryNarrative] = useState(() => loadState('storyNarrative', ""));
  
  const [masterCharacters, setMasterCharacters] = useState<MasterCharacter[]>(() => loadState('masterCharacters', []));
  const [sceneBreakdown, setSceneBreakdown] = useState<SceneBreakdown[]>(() => loadState('sceneBreakdown', []));
  
  const [currentStage, setCurrentStage] = useState(() => loadState('currentStage', 0));
  const [styleReferenceUrl, setStyleReferenceUrl] = useState(() => loadState('styleReferenceUrl', ""));
  const [stylePrompt, setStylePrompt] = useState(() => loadState('stylePrompt', ""));
  const [isAutoRun, setIsAutoRun] = useState(false);

  // Persist storage whenever key fields change
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const stateToSave = {
        videoLength,
        videoType,
        storyIdea,
        storyNarrative,
        masterCharacters,
        sceneBreakdown,
        currentStage,
        styleReferenceUrl,
        stylePrompt
      };
      localStorage.setItem('projectState', JSON.stringify(stateToSave));
    }
  }, [videoLength, videoType, storyIdea, storyNarrative, masterCharacters, sceneBreakdown, currentStage, styleReferenceUrl, stylePrompt]);

  // Removed the secondary useEffect for loading since we now load lazily


  const updateCharacter = (id: string, updates: Partial<MasterCharacter>) => {
    setMasterCharacters(prev => 
      prev.map(char => char.id === id ? { ...char, ...updates } : char)
    );
  };

  const updateScene = (index: number, updates: Partial<SceneBreakdown>) => {
    setSceneBreakdown(prev => {
      const newScenes = [...prev];
      if (newScenes[index]) {
        newScenes[index] = { ...newScenes[index], ...updates };
      }
      return newScenes;
    });
  };

  return (
    <ProjectContext.Provider value={{
      videoLength,
      videoType,
      setVideoLength,
      setVideoType,
      storyIdea,
      storyNarrative,
      setStoryIdea,
      setStoryNarrative,
      masterCharacters,
      setMasterCharacters,
      updateCharacter,
      sceneBreakdown,
      setSceneBreakdown,
      updateScene,
      currentStage,
      setCurrentStage,
      styleReferenceUrl,
      setStyleReferenceUrl,
      stylePrompt,
      setStylePrompt,
      isAutoRun,
      setIsAutoRun
    }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
}
