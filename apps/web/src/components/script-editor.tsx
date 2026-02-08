"use client";

import { useProject } from "@/context/project-context";
import { useNiche } from "@/context/niche-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState, useEffect, useRef } from "react";
import { v4 as uuidv4 } from 'uuid';
import { parseManualScript } from "@/lib/script-parser";

export function ScriptEditor() {
  const { selectedNicheId, channels } = useNiche();
  const { 
    videoLength, setVideoLength,
    videoType, setVideoType,
    storyIdea, setStoryIdea,
    storyNarrative, setStoryNarrative,
    masterCharacters, setMasterCharacters, updateCharacter,
    setSceneBreakdown,
    currentStage, setCurrentStage,
    setStyleReferenceUrl, styleReferenceUrl,
    setStylePrompt, stylePrompt,
    isAutoRun, setIsAutoRun 
  } = useProject();

  const [isGeneratingStory, setIsGeneratingStory] = useState(false);
  const [isGeneratingBreakdown, setIsGeneratingBreakdown] = useState(false);
  const [isGeneratingStyle, setIsGeneratingStyle] = useState(false);
  const [manualScriptInfo, setManualScriptInfo] = useState("");
  const [isExtractingManual, setIsExtractingManual] = useState(false);
  const isAutoGeneratingRef = useRef(false);

  // Unified Manual Script Extraction (LLM-Powered)
  const handleManualExtraction = async (autoRun: boolean) => {
    if (!manualScriptInfo) return;
    
    setIsExtractingManual(true);
    try {
        console.log("🧠 Requesting LLM Extraction for Manual Script...");
        const res = await fetch("http://127.0.0.1:8000/scripts/generate-breakdown", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                story_narrative: manualScriptInfo, // Manual script is passed as the "narrative"
                video_length: videoLength,
                video_type: videoType,
                niche_id: selectedNicheId
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Extraction failed" }));
            throw new Error(err.detail);
        }
        
        const data = await res.json();
        
        if (!data.scenes || data.scenes.length === 0) {
            throw new Error("No scenes were extracted. Please check your script format.");
        }

        // Init characters with client-side IDs
        const chars = data.characters.map((c: any) => ({
            ...c,
            id: uuidv4(),
            locked: false,
            isGenerating: false
        }));
        
        setMasterCharacters(chars);
        setSceneBreakdown(data.scenes.map((s: any) => ({ 
            ...s, 
            isGeneratingImage: false, 
            isGeneratingVideo: false 
        })));
        
        setVideoType("story");
        setIsAutoRun(autoRun);
        setCurrentStage(2); // Go to Master Characters
        
    } catch (e: any) {
        console.error("Extraction Error:", e);
        alert(`Extraction Failed: ${e.message}`);
    } finally {
        setIsExtractingManual(false);
    }
  };
  
  // --- AUTO-RUN LOGIC: Stage 2 (Cast) ---
  // If isAutoRun is true and we are in Stage 2, generate characters one by one then move to Stage 3
  // MOVED TO TOP LEVEL TO RESPECT REACT HOOK RULES
  useEffect(() => {
      if (isAutoRun && currentStage === 2 && masterCharacters.length > 0) {
          // Find next un-generated character
          const nextChar = masterCharacters.find(c => !c.imageUrl && !c.isGenerating);
          const anyGenerating = masterCharacters.some(c => c.isGenerating);
          
          if (nextChar && !anyGenerating && !isAutoGeneratingRef.current) {
             // Generate it
             const generateOne = async () => {
                  isAutoGeneratingRef.current = true;
                 updateCharacter(nextChar.id, { isGenerating: true });
                 try {
                      console.log(`🤖 Auto-Run: Generating ${nextChar.name}...`);
                      const res = await fetch("http://127.0.0.1:8000/characters/generate-image", {
                          method: "POST",
                          headers: {"Content-Type": "application/json"},
                          body: JSON.stringify({
                               character_name: nextChar.name,
                              prompt: nextChar.prompt,
                              niche_id: selectedNicheId,
                              is_shorts: videoLength === "short"
                          })
                      });
                      
                      if (!res.ok) {
                          const err = await res.json();
                          throw new Error(err.detail || "Server error");
                      }
                      
                      const data = await res.json();
                      if (data.imageUrl) {
                          updateCharacter(nextChar.id, { imageUrl: data.imageUrl, locked: true });
                      }
                 } catch (e: any) {
                     console.error("Auto-Run Cast Error:", e);
                     setIsAutoRun(false); // Stop auto-run on error
                     // alert(`Auto-Run Cast Failed: ${e.message}`); // Removed for 1-Step stability
                 } finally {
                     isAutoGeneratingRef.current = false;
                     updateCharacter(nextChar.id, { isGenerating: false });
                 }
             };
             generateOne();
          } else {
              // Check if all are done
              const allDone = masterCharacters.every(c => c.imageUrl);
              const anyGenerating = masterCharacters.some(c => c.isGenerating);
              
              if (allDone && !anyGenerating) {
                  console.log("🤖 Auto-Run: All characters done. Moving to Stage 3 (Scenes)...");
                  setCurrentStage(3);
              }
          }
      }
  }, [isAutoRun, currentStage, masterCharacters, updateCharacter, selectedNicheId, setCurrentStage, setIsAutoRun]);

  const currentChannelName = channels.find(c => c.id === selectedNicheId)?.name;

  // --- STAGE 0: Settings & Story Idea ---
  if (currentStage === 0) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
             <CardTitle className="flex justify-between items-center">
                 <span>🎥 Concept & Settings</span>
                 {currentChannelName && <Badge variant="outline">{currentChannelName}</Badge>}
             </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
             {/* 1. Video Length */}
             <div className="space-y-2">
                 <label className="text-sm font-medium">Video Length</label>
                 <div className="flex gap-4">
                     <label className={`flex items-center gap-2 cursor-pointer border p-3 rounded-md w-full ${videoLength === "short" ? 'bg-primary/10 border-primary' : ''}`}>
                         <input type="radio" name="len" checked={videoLength === "short"} onChange={() => setVideoLength("short")} className="w-4 h-4"/>
                         <div>
                             <span className="font-bold block">📱 Short (9:16)</span>
                             <span className="text-xs text-muted-foreground">~12 Scenes (TikTok/Reels)</span>
                         </div>
                     </label>
                     <label className={`flex items-center gap-2 cursor-pointer border p-3 rounded-md w-full ${videoLength === "long" ? 'bg-primary/10 border-primary' : ''}`}>
                         <input type="radio" name="len" checked={videoLength === "long"} onChange={() => setVideoLength("long")} className="w-4 h-4"/>
                         <div>
                             <span className="font-bold block">📺 Long (16:9)</span>
                             <span className="text-xs text-muted-foreground">40-50 Scenes (YouTube)</span>
                         </div>
                     </label>
                 </div>
             </div>
             
             {/* 2. Video Type */}
             <div className="space-y-2">
                 <label className="text-sm font-medium">Format Style</label>
                 <div className="flex gap-4">
                     <label className={`flex items-center gap-2 cursor-pointer border p-3 rounded-md w-full ${videoType === "story" ? 'bg-primary/10 border-primary' : ''}`}>
                         <input type="radio" name="type" checked={videoType === "story"} onChange={() => setVideoType("story")} className="w-4 h-4"/>
                         <div>
                             <span className="font-bold block">🎭 Story Mode</span>
                             <span className="text-xs text-muted-foreground">Animated characters with dialogue (Grok)</span>
                         </div>
                     </label>
                     <label className={`flex items-center gap-2 cursor-pointer border p-3 rounded-md w-full ${videoType === "documentary" ? 'bg-primary/10 border-primary' : ''}`}>
                         <input type="radio" name="type" checked={videoType === "documentary"} onChange={() => setVideoType("documentary")} className="w-4 h-4"/>
                         <div>
                             <span className="font-bold block">📚 Documentary</span>
                             <span className="text-xs text-muted-foreground">Voiceover narration + B-roll</span>
                         </div>
                     </label>
                 </div>
             </div>


             {/* 3. Story Input Mode */}
             <div className="space-y-2">
                 <label className="text-sm font-medium">Story Content</label>
                 
                 <Tabs defaultValue="generator" className="w-full">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="generator">✨ AI Generator</TabsTrigger>
                        <TabsTrigger value="manual">📝 Manual Script</TabsTrigger>
                    </TabsList>

                    {/* AI GENERATOR TAB */}
                    <TabsContent value="generator" className="space-y-4 pt-4">
                        <div className="space-y-2">
                            <label className="text-sm text-muted-foreground">Story Concept / Idea</label>
                            <Textarea 
                                placeholder="e.g., A lonely boy finds a lost baby dragon in the forest and tries to hide it from his parents..."
                                rows={6}
                                value={storyIdea}
                                onChange={(e) => setStoryIdea(e.target.value)}
                            />
                        </div>
                        <div className="flex justify-end">
                             <Button 
                               size="lg" 
                               disabled={!storyIdea || !selectedNicheId || isGeneratingStory}
                               onClick={async () => {
                                   setIsGeneratingStory(true);
                                   try {
                                       const res = await fetch("http://127.0.0.1:8000/scripts/generate-story", {
                                           method: "POST",
                                           headers: {"Content-Type": "application/json"},
                                           body: JSON.stringify({
                                               story_idea: storyIdea,
                                               video_length: videoLength,
                                               niche_id: selectedNicheId
                                           })
                                       });
                                       if (!res.ok) {
                                           const errData = await res.json().catch(() => ({ detail: res.statusText }));
                                           throw new Error(errData.detail || "Failed to generate story");
                                       }
                                       const data = await res.json();
                                       setStoryNarrative(data.narrative);
                                       console.log("Moving to Stage 1: Story Review");
                                       setCurrentStage(1); // Move to Stage 1
                                   } catch (e: any) {
                                       console.error(e);
                                       alert(`Error: ${e.message}`);
                                   } finally {
                                       setIsGeneratingStory(false);
                                   }
                               }}
                             >
                                 {isGeneratingStory ? "✨ Generating..." : "🤖 Generate Story"}
                             </Button>
                        </div>
                    </TabsContent>

                    {/* MANUAL SCRIPT TAB */}
                    <TabsContent value="manual" className="space-y-4 pt-4">
                        <div className="p-4 bg-muted/30 rounded-md border text-sm text-muted-foreground">
                            <p className="font-semibold mb-2">📋 Paste your full script below.</p>
                            <ul className="list-disc pl-5 space-y-1 text-xs">
                                <li><strong>Master Characters:</strong> "🧒 [Name]" followed by "Text-to-Image Prompt:"</li>
                                <li><strong>Scenes:</strong> "🎞️ SCENE X" header</li>
                                <li>Includes Shot Type, Prompts, and Dialogue</li>
                            </ul>
                        </div>
                        <Textarea 
                            placeholder={`Master Chracters:\n🧒 [BOY 1]...\n\nSCENES:\n🎞️ SCENE 1...\nShot Type:...\nText-to-Image Prompt\n...`}
                            rows={15}
                            className="font-mono text-xs"
                            onChange={(e) => setManualScriptInfo(e.target.value)}
                        />
                         <div className="flex gap-4 justify-end">
                            <Button
                                size="lg"
                                variant="outline"
                                disabled={!manualScriptInfo || isExtractingManual}
                                onClick={() => handleManualExtraction(false)}
                            >
                                {isExtractingManual ? "🧠 Extracting..." : "📝 Proceed Manually"}
                            </Button>

                              <Button 
                                size="lg" 
                                className="bg-purple-600 hover:bg-purple-700 text-white"
                                disabled={!manualScriptInfo || isExtractingManual}
                                onClick={() => handleManualExtraction(true)}
                             >
                                 {isExtractingManual ? "🚀 Starting..." : "🚀 1-Step Automation"}
                              </Button>
                        </div>
                    </TabsContent>
                 </Tabs>
             </div>
           </CardContent>
         </Card>
      </div>
    );
  }

  // --- STAGE 1: Story Review ---
  if (currentStage === 1) {
      return (
          <div className="space-y-6">
              <div className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer" onClick={() => setCurrentStage(0)}>
                  ← Back to Settings
              </div>
              <Card>
                  <CardHeader>
                      <CardTitle>📖 Story Narrative</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                      <Textarea 
                          className="min-h-[400px] text-lg leading-relaxed font-serif"
                          value={storyNarrative}
                          onChange={(e) => setStoryNarrative(e.target.value)}
                      />
                      <div className="flex justify-between">
                          <Button variant="outline" onClick={() => setCurrentStage(0)}>Edit Concept</Button>
                          <Button 
                              size="lg"
                              disabled={isGeneratingBreakdown}
                              onClick={async () => {
                                  setIsGeneratingBreakdown(true);
                                  try {
                                      const res = await fetch("http://127.0.0.1:8000/scripts/generate-breakdown", {
                                          method: "POST",
                                          headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify({
                                              story_narrative: storyNarrative,
                                              video_length: videoLength,
                                              video_type: videoType,
                                              niche_id: selectedNicheId
                                          })
                                      });
                                      if (!res.ok) throw new Error("Breakdown generation failed");
                                      const data = await res.json();
                                      
                                      // Init characters with client-side IDs
                                      const chars = data.characters.map((c: any) => ({
                                          ...c,
                                          id: uuidv4(),
                                          locked: false,
                                          isGenerating: false
                                      }));
                                      
                                      setMasterCharacters(chars);
                                      setSceneBreakdown(data.scenes);
                                      
                                      // AUTO-ADVANCE TRIGGER
                                      // User wants to go straight to processing
                                      setIsAutoRun(true); 
                                      
                                      setCurrentStage(2); // Go to Master Characters
                                  } catch (e) {
                                      alert(e);
                                  } finally {
                                      setIsGeneratingBreakdown(false);
                                  }
                              }}
                          >
                              {isGeneratingBreakdown ? "⚙️ Generating..." : "🚀 1-Step Automation"}
                          </Button>
                          <Button 
                              size="lg"
                              variant="outline"
                              disabled={isGeneratingBreakdown}
                              onClick={async () => {
                                  // Manual Process Logic (Same as above basically, minus auto-run)
                                  setIsGeneratingBreakdown(true);
                                  try {
                                      const res = await fetch("http://127.0.0.1:8000/scripts/generate-breakdown", {
                                          method: "POST",
                                          headers: {"Content-Type": "application/json"},
                                          body: JSON.stringify({
                                              story_narrative: storyNarrative,
                                              video_length: videoLength,
                                              video_type: videoType,
                                              niche_id: selectedNicheId
                                          })
                                      });
                                      if (!res.ok) throw new Error("Breakdown generation failed");
                                      const data = await res.json();
                                      
                                      const chars = data.characters.map((c: any) => ({ ...c, id: uuidv4(), locked: false, isGenerating: false }));
                                      setMasterCharacters(chars);
                                      setSceneBreakdown(data.scenes);
                                      
                                      setIsAutoRun(false); // Manual Mode
                                      setCurrentStage(2);
                                  } catch (e) { alert(e); } finally { setIsGeneratingBreakdown(false); }
                              }}
                          >
                              📝 Proceed Manually
                          </Button>
                      </div>
                  </CardContent>
              </Card>
          </div>
      );
  }

  // --- STAGE 2: Master Characters ---
  if (currentStage === 2) {
      return (
          <div className="space-y-6">
               <div className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer" onClick={() => setCurrentStage(1)}>
                  ← Back to Story
              </div>
              
              <div className="flex justify-between items-center">
                  <h2 className="text-2xl font-bold">🎭 Master Cast</h2>
                  <Button 
                      size="lg" 
                      disabled={masterCharacters.some(c => !c.locked)}
                      onClick={() => setCurrentStage(3)} // Move to Scenes Tab
                  >
                      Finalize Cast & Go to Scenes ➡️
                  </Button>
              </div>
              
              <div className="grid grid-cols-2 gap-6">
                  {/* MASTER STYLE CARD */}
                  {/* MASTER STYLE CARD REMOVED AS PER USER REQUEST */}

                  {masterCharacters.map((char) => (
                      <Card key={char.id} className={char.locked ? "border-green-500 bg-green-50/10" : ""}>
                          <CardHeader className="pb-2">
                              <CardTitle className="flex justify-between">
                                  <span>{char.name}</span>
                                  {char.locked && <Badge className="bg-green-500">🔒 Locked</Badge>}
                              </CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-4">
                              <div className="flex gap-4">
                                  {/* Image Preview Area */}
                                  <div className="w-1/3 aspect-square bg-muted rounded-md relative overflow-hidden flex items-center justify-center">
                                      {char.imageUrl ? (
                                          <img src={char.imageUrl} alt={char.name} className="w-full h-full object-cover"/>
                                      ) : (
                                          <div className="text-center p-2 text-xs text-muted-foreground">
                                              {char.isGenerating ? "🎨 Generating..." : "No Image"}
                                          </div>
                                      )}
                                  </div>
                                  
                                  {/* Prompt & Controls */}
                                  <div className="flex-1 space-y-3">
                                      <Textarea 
                                          value={char.prompt}
                                          onChange={(e) => updateCharacter(char.id, { prompt: e.target.value })}
                                          rows={4}
                                          className="text-sm"
                                          disabled={char.locked}
                                      />
                                      <div className="flex gap-2">
                                          <Button 
                                              size="sm" 
                                              variant="default"
                                              disabled={char.locked || char.isGenerating}
                                              className="flex-1"
                                              onClick={async () => {
                                                  updateCharacter(char.id, { isGenerating: true });
                                                  try {
                                                      console.log(`🎨 Requesting character generation for ${char.name}...`);
                                                      const res = await fetch("http://127.0.0.1:8000/characters/generate-image", {
                                                          method: "POST",
                                                          headers: {"Content-Type": "application/json"},
                                                          body: JSON.stringify({
                                                              character_name: char.name,
                                                              prompt: char.prompt,
                                                              niche_id: selectedNicheId,
                                                              is_shorts: videoLength === "short"
                                                          })
                                                      });
                                                      
                                                      if (!res.ok) {
                                                          const err = await res.json();
                                                          throw new Error(err.detail || "Server error");
                                                      }

                                                      const data = await res.json();
                                                      console.log("✅ Character image generated:", data.imageUrl);
                                                      updateCharacter(char.id, { imageUrl: data.imageUrl });
                                                   } catch (e: any) {
                                                       console.error("❌ Character Generation Error:", e);
                                                       if (!isAutoRun) alert(`Generation Failed: ${e.message}`);
                                                   } finally {
                                                      updateCharacter(char.id, { isGenerating: false });
                                                  }
                                              }}
                                          >
                                              {char.imageUrl ? "🔄 Regenerate" : "🎨 Generate Image"}
                                          </Button>
                                          
                                          {char.imageUrl && !char.locked && (
                                              <Button 
                                                  size="sm" 
                                                  variant="outline"
                                                  className="text-green-600 border-green-200 hover:bg-green-50"
                                                  onClick={() => updateCharacter(char.id, { locked: true })}
                                              >
                                                  🔒 Lock
                                              </Button>
                                          )}
                                          
                                          {char.locked && (
                                              <Button 
                                                  size="sm" 
                                                  variant="outline"
                                                  onClick={() => updateCharacter(char.id, { locked: false })}
                                              >
                                                  🔓 Unlock
                                              </Button>
                                          )}
                                      </div>
                                  </div>
                              </div>
                          </CardContent>
                      </Card>
                  ))}
              </div>
          </div>
      );
  }

  return null;
}
