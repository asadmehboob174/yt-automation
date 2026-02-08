"use client";

import { useProject } from "@/context/project-context";
import { useNiche } from "@/context/niche-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect, useRef } from "react";

export function SceneImages() {
  const { selectedNicheId, channels } = useNiche();
  const { 
    masterCharacters, 
    sceneBreakdown, updateScene,
    setCurrentStage,
    videoLength,
    styleReferenceUrl,
    isAutoRun 
  } = useProject();


  const [isBulkGenerating, setIsBulkGenerating] = useState(false);
  const hasAutoRunStarted = useRef(false);

  // --- SINGLE IMAGE GENERATION (Retry/Manual) ---
  const generateImage = async (index: number) => {
    const scene = sceneBreakdown[index];
    updateScene(index, { isGeneratingImage: true });
    
    try {
      // Prepare character references for consistency
      const characterRefs = masterCharacters
        .filter(c => c.locked && c.imageUrl)
        .map(c => ({ name: c.name, imageUrl: c.imageUrl, prompt: c.prompt }));

      const res = await fetch("http://127.0.0.1:8000/scenes/generate-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scene_index: index,
          prompt: scene.text_to_image_prompt,
          niche_id: selectedNicheId,
          character_images: characterRefs
        })
      });

      if (!res.ok) throw new Error("Generation failed");
      const data = await res.json();
      
      updateScene(index, { imageUrl: data.imageUrl });
    } catch (err) {
      console.error(err);
      if (!isAutoRun) alert(`Failed to generate scene ${index + 1}`);
    } finally {
      updateScene(index, { isGeneratingImage: false });
    }
  };

  // --- BATCH IMAGE GENERATION (Efficient Single-Session) ---
  const generateAllImages = async () => {
    if (isBulkGenerating) return;
    setIsBulkGenerating(true);

    const pendingIndices = sceneBreakdown
        .map((s, i) => (!s.imageUrl ? i : -1))
        .filter(i => i !== -1);

    if (pendingIndices.length === 0) {
        setIsBulkGenerating(false);
        return;
    }

    // Mark all as generating
    pendingIndices.forEach(i => updateScene(i, { isGeneratingImage: true }));

    try {
        const characterRefs = masterCharacters
            .filter(c => c.locked && c.imageUrl)
            .map(c => ({ name: c.name, imageUrl: c.imageUrl, prompt: c.prompt }));
            
        // Collect prompts in order
        const prompts = pendingIndices.map(i => sceneBreakdown[i].text_to_image_prompt);

        console.log(`🚀 Starting Batch Generation for ${prompts.length} scenes...`);

        const res = await fetch("http://127.0.0.1:8000/scenes/generate-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompts: prompts,
                niche_id: selectedNicheId,
                is_shorts: false, // Default landscape for scenes
                style_suffix: "", // Backend handles from Niche ID
                character_images: characterRefs
            })
        });

        if (!res.ok) throw new Error("Batch generation failed");
        
        const data = await res.json();
        const urls = data.imageUrls; // Array of URLs (or nulls)

        // Assign results back to scenes
        // The backend returns results in the same order as prompts
        urls.forEach((url: string | null, idx: number) => {
            const sceneIndex = pendingIndices[idx];
            if (url) {
                updateScene(sceneIndex, { imageUrl: url });
            }
            updateScene(sceneIndex, { isGeneratingImage: false });
        });

    } catch (err) {
        console.error("Batch Error:", err);
        pendingIndices.forEach(i => updateScene(i, { isGeneratingImage: false }));
    } finally {
        setIsBulkGenerating(false);
    }
  };


  // --- AUTO-RUN TRIGGER ---
  useEffect(() => {
    if (isAutoRun && !hasAutoRunStarted.current) {
        // Check if we need to generate images
        const needsGen = sceneBreakdown.some(s => !s.imageUrl);
        
        if (needsGen) {
            console.log("🤖 Auto-Run: Starting Batch Image Generation...");
            hasAutoRunStarted.current = true;
            generateAllImages();
        } else {
            // Already done? Move on?
            // hasAutoRunStarted.current = true; // prevent loop
        }
    }
    
    // Auto-Advance if all done
    const allComplete = sceneBreakdown.length > 0 && sceneBreakdown.every(s => s.imageUrl);
    if (isAutoRun && allComplete && !isBulkGenerating) {
        console.log("🤖 Auto-Run: All scenes images done. Moving to Stage 4...");
        if (!hasAutoRunStarted.current) hasAutoRunStarted.current = true; // Ensure flagged
        const t = setTimeout(() => setCurrentStage(4), 1500);
        return () => clearTimeout(t);
    }

  }, [isAutoRun, sceneBreakdown, isBulkGenerating, setCurrentStage]);


  return (
    <div className="space-y-6">
      {/* 1. Master Characters Header */}
      {/* 1. Style Reference Header */}
      {styleReferenceUrl && (
        <Card className="bg-purple-50/10 border-purple-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              🎨 Active Style Reference
            </CardTitle>
          </CardHeader>
          <CardContent>
             <div className="flex gap-4 items-center">
                <div className="w-32 aspect-video bg-muted rounded-md overflow-hidden border border-purple-300">
                    <img src={styleReferenceUrl} className="w-full h-full object-cover" />
                </div>
                <div className="text-sm text-muted-foreground">
                    <p>All scenes will be generated using this style reference.</p>
                </div>
             </div>
          </CardContent>
        </Card>
      )}

      {/* 1.5. Locked Characters Header */}
      {masterCharacters.some(c => c.locked && c.imageUrl) && (
        <Card className="bg-muted/30">
          <CardHeader className="py-2 px-4">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              🎭 Locked Cast Reference
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
             <div className="flex gap-4 overflow-x-auto pb-2">
                {masterCharacters.filter(c => c.locked && c.imageUrl).map(char => (
                  <div key={char.id} className="flex-shrink-0 space-y-1">
                    <div className="w-16 h-16 rounded-md overflow-hidden border-2 border-primary/20 relative">
                        <img src={char.imageUrl} alt={char.name} className="w-full h-full object-cover" />
                        <div className="absolute top-0 right-0 p-0.5 bg-primary/80 text-[8px] text-white rounded-bl">🔒</div>
                    </div>
                    <p className="text-[10px] font-medium text-center truncate w-16">{char.name}</p>
                  </div>
                ))}
             </div>
          </CardContent>
        </Card>
      )}

      {/* 2. Scenes List */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold">Scene Images</h2>
          <Button 
            onClick={generateAllImages} 
            disabled={isBulkGenerating || sceneBreakdown.length === 0}
          >
            {isBulkGenerating ? "generating..." : "🚀 Generate All Images"}
          </Button>
        </div>

        {sceneBreakdown.map((scene, i) => (
          <Card key={i}>
            <CardContent className="p-4 flex gap-4">
              <div className="w-1/3 aspect-video bg-muted rounded-md relative overflow-hidden flex items-center justify-center group">
                 {scene.imageUrl ? (
                   <img src={scene.imageUrl} alt={`Scene ${scene.scene_number}`} className="w-full h-full object-cover" />
                 ) : (
                   <span className="text-muted-foreground text-sm">
                     {scene.isGeneratingImage ? "🎨 Generating..." : "Image Pending..."}
                   </span>
                 )}
                 {scene.imageUrl && (
                   <Button 
                     size="sm" 
                     variant="secondary" 
                     className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                     onClick={() => generateImage(i)}
                   >
                     🔄 Regenerate
                   </Button>
                 )}
              </div>
              <div className="flex-1 space-y-2">
                <div className="flex justify-between">
                  <h3 className="font-bold">{scene.scene_number}. {scene.scene_title}</h3>
                  <div className="flex gap-2">
                    <Button 
                      size="sm" 
                      onClick={() => generateImage(i)}
                      disabled={scene.isGeneratingImage}
                    >
                      {scene.imageUrl ? "🔄 Re-roll" : "🖼️ Generate"}
                    </Button>
                    <Button size="icon" variant="secondary" className="h-8 w-8">
                      ✏️
                    </Button>
                  </div>
                </div>
                <div className="text-sm text-muted-foreground bg-muted/50 p-2 rounded">
                  <span className="font-semibold text-foreground">Prompt: </span>
                  {scene.text_to_image_prompt}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        
        {sceneBreakdown.length === 0 && (
            <div className="text-center py-10 text-muted-foreground">
                No scenes available. Complete the script breakdown first.
            </div>
        )}
      </div>

      <div className="flex justify-end pt-6">
        <Button 
          size="lg" 
          onClick={() => setCurrentStage(4)}
          disabled={sceneBreakdown.some(s => !s.imageUrl)} // Force all images generated? Maybe optional.
        >
          Proceed to Animation ➡️
        </Button>
      </div>
    </div>
  );
}
