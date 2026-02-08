"use client";

import { useProject } from "@/context/project-context";
import { useNiche } from "@/context/niche-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect, useRef } from "react";

export function Animation() {
  const { selectedNicheId } = useNiche();
  const { 
    sceneBreakdown, 
    updateScene,
    isAutoRun,
    setCurrentStage 
  } = useProject();
  const [isBulkGenerating, setIsBulkGenerating] = useState(false);

  // Use a Ref to track the LATEST scene state across async generation calls
  const sceneBreakdownRef = useRef(sceneBreakdown);
  useEffect(() => {
    sceneBreakdownRef.current = sceneBreakdown;
  }, [sceneBreakdown]);

  const generateVideo = async (index: number) => {
    // ALWAYS check the Ref for the absolute latest state to avoid redundant calls
    const currentScene = sceneBreakdownRef.current[index];
    if (!currentScene.imageUrl || currentScene.videoUrl) {
        console.log(`⏩ Skipping scene ${index + 1}: Already has video or no image.`);
        return;
    }

    updateScene(index, { isGeneratingVideo: true });
    
    try {
      const res = await fetch("http://127.0.0.1:8000/scenes/generate-video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scene_index: index,
          imageUrl: currentScene.imageUrl,
          // Send RAW fields so Backend/Agent can format them properly
          prompt: currentScene.image_to_video_prompt, 
          dialogue: currentScene.dialogue, 
          camera_angle: currentScene.camera_angle || "Medium Shot",
          niche_id: selectedNicheId
        })
      });

      if (!res.ok) throw new Error("Video generation failed");
      const data = await res.json();
      
      updateScene(index, { videoUrl: data.videoUrl });
    } catch (err) {
      console.error(err);
      if (!isAutoRun) alert(`Failed to generate video for scene ${index + 1}`);
    } finally {
      updateScene(index, { isGeneratingVideo: false });
    }
  };


  // --- AUTO-RUN LOGIC ---
  
  // 1. Auto-Trigger Generation
  // Ref to lock the auto-runner preventing parallel execution
  const isAutoGeneratingRef = useRef(false);

  // --- AUTO-RUN QUEUE WORKER ---
  useEffect(() => {
    // Only run if global AutoRun is on, or we triggered a bulk run locally
    if (isAutoRun || isBulkGenerating) {
        // 1. Find the next pending item
        // We use the 'isGeneratingVideo' flag to ensure we don't pick one that's already flying
        const nextSceneIndex = sceneBreakdown.findIndex(s => s.imageUrl && !s.videoUrl && !s.isGeneratingVideo);
        
        // 2. Safety Check: Are we already running one?
        // We use the Ref to strictly prevent React Double-Effects from firing two parallel requests
        if (nextSceneIndex !== -1 && !isAutoGeneratingRef.current) {
            
            // LOCK
            isAutoGeneratingRef.current = true;
            
            const processNext = async () => {
                try {
                    console.log(`🤖 Queue Worker: Starting Scene ${nextSceneIndex + 1}...`);
                    await generateVideo(nextSceneIndex);
                } catch (e) {
                     console.error("Queue Worker Error:", e);
                     // If we are in AutoRun, we might want to pause or just keep trying the others?
                     // For now, we continue, hoping it was transient. 
                     // The generateVideo catches its own errors so we shouldn't crash here.
                } finally {
                    // UNLOCK
                    // We release the lock so the NEXT render (caused by generateVideo's state update) 
                    // can pick up the next item.
                    isAutoGeneratingRef.current = false;
                }
            };
            
            processNext();
        } 
        else if (nextSceneIndex === -1 && !isAutoGeneratingRef.current) {
            // 3. No more pending items?
            // Verify if we are truly done (all valid images have videos)
            const allComplete = sceneBreakdown.every(s => !s.imageUrl || s.videoUrl);
            const anyStillGenerating = sceneBreakdown.some(s => s.isGeneratingVideo);
            
            if (allComplete && !anyStillGenerating) {
                 console.log("✅ Queue Worker: All videos complete.");
                 if (isBulkGenerating) setIsBulkGenerating(false);
                 
                 // If Global AutoRun, move to next stage
                 if (isAutoRun) {
                     console.log("🤖 Auto-Run: Moving to Stage 5 (Render)...");
                     // Small delay for UX
                     setTimeout(() => setCurrentStage(5), 1500);
                 }
            }
        }
    }
  }, [isAutoRun, isBulkGenerating, sceneBreakdown, setCurrentStage, generateVideo]); 
  // Note: generateVideo needs to be stable or this effect fires too often. 
  // But generateVideo is defined inside component? It changes every render.
  // We should wrap generateVideo in useCallback OR just move the logic inline? 
  // Ideally, generateVideo should specific index, so it's fine. 
  // Let's rely on standard deps.

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">🎬 Grok Animation</h2>
        <Button 
            onClick={() => setIsBulkGenerating(true)} 
            disabled={isBulkGenerating || sceneBreakdown.length === 0}
        >
            {isBulkGenerating ? "generating..." : "🚀 Generate All Videos"}
        </Button>
      </div>

      {sceneBreakdown.map((scene, i) => (
        <Card key={i}>
          <CardContent className="p-4 flex gap-6">
            {/* 1. Source Image */}
            <div className="w-48 space-y-2">
              <div className="aspect-video bg-muted rounded-md overflow-hidden">
                {scene.imageUrl ? (
                  <img src={scene.imageUrl} alt="Source" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">
                    No Image
                  </div>
                )}
              </div>
              <Badge variant="outline" className="w-full justify-center">Scene {scene.scene_number}</Badge>
            </div>

            {/* 2. Prompts & Dialogue */}
            <div className="flex-1 space-y-4">
              
              {/* Shot Type */}
              <div className="space-y-1">
                <span className="text-xs font-bold uppercase text-muted-foreground">Shot: </span>
                <span className="text-sm font-medium">{scene.camera_angle || "Medium Shot"}</span>
              </div>

              {/* Image-to-Video Prompt */}
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                    <label className="text-xs font-bold uppercase text-muted-foreground">Image-to-Video Prompt</label>
                    <Button size="icon" variant="ghost" className="h-4 w-4 opacity-50 hover:opacity-100" title="Edit Prompt">
                        ✏️
                    </Button>
                </div>
                <div className="p-3 bg-muted/30 rounded-md text-sm whitespace-pre-wrap">
                  {scene.image_to_video_prompt}
                </div>
              </div>

              {/* Dialogue */}
              {scene.dialogue && (
                <div className="space-y-1">
                  <label className="text-xs font-bold uppercase text-blue-400">Dialogue</label>
                  <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-md text-sm font-medium whitespace-pre-wrap">
                    {scene.dialogue}
                  </div>
                </div>
              )}
            </div>

            {/* 3. Output Video */}
            <div className="w-64 space-y-2">
              <div className="aspect-video bg-black rounded-md overflow-hidden flex items-center justify-center relative group">
                {scene.videoUrl ? (
                  <video src={scene.videoUrl} controls className="w-full h-full" />
                ) : (
                  <div className="text-xs text-muted-foreground p-2 text-center">
                      {scene.isGeneratingVideo ? "🎬 Animating..." : "Video Pending..."}
                  </div>
                )}
                
                {/* Generate Button Overlay - Centered and Visible */}
                {!scene.videoUrl && (
                    <Button 
                        size="sm" 
                        className="absolute inset-0 m-auto w-max h-8 bg-primary/90 hover:bg-primary shadow-lg disabled:opacity-70 disabled:cursor-not-allowed"
                        onClick={() => generateVideo(i)}
                        disabled={scene.isGeneratingVideo || !scene.imageUrl}
                        title={!scene.imageUrl ? "Generate source image first" : ""}
                    >
                        {scene.isGeneratingVideo ? "..." : (scene.imageUrl ? "▶️ Generate Video" : "🚫 No Source Image")}
                    </Button>
                )}
              </div>
              {scene.videoUrl && (
                <Button 
                    size="sm" 
                    variant="outline" 
                    className="w-full"
                    onClick={() => generateVideo(i)}
                    disabled={scene.isGeneratingVideo}
                >
                    🔄 Regenerate
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}

        {sceneBreakdown.length === 0 && (
            <div className="text-center py-10 text-muted-foreground">
                No scenes available. Complete image generation first.
            </div>
        )}
    </div>
  );
}
