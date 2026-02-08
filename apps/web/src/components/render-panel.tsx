"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState, useEffect } from "react";
import { useProject } from "@/context/project-context";
import { useNiche } from "@/context/niche-context";
import { AlertCircle, CheckCircle, Upload, Download } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function RenderPanel() {
  const { selectedNicheId, channels } = useNiche();
  const { 
    sceneBreakdown, 
    storyIdea, 
    storyNarrative, 
    videoType,
    masterCharacters,
    updateScene, // Added for regeneration
    isAutoRun,
    setIsAutoRun 
  } = useProject();

  const [hasAutoStitchRun, setHasAutoStitchRun] = useState(false);
  
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("IDLE"); // IDLE, QUEUED, PROCESSING, REVIEW_PENDING, UPLOADING, COMPLETED, FAILED
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("Ready to start render pipeline");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [musicUrl, setMusicUrl] = useState<string | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [settings, setSettings] = useState({
    kenBurns: true,
    sidechain: true,
    quality: "1080p",
    subtitleStyle: "yellow",
    musicMood: "auto", // Default
  });

  const MUSIC_OPTIONS = [
      { value: "auto", label: "✨ Auto-Detect (AI)", url: "" },
      { value: "cute", label: "😊 Cute / Vlog (Wallpaper)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3" },
      { value: "travel", label: "✈️ Travel (Life of Riley)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Life%20of%20Riley.mp3" },
      { value: "calm", label: "😌 Calm (Clear Waters)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clear%20Waters.mp3" },
      { value: "peace", label: "🕊️ Peace (Porch Swing)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Porch%20Swing%20Days%20-%20slower.mp3" },
      { value: "beauty", label: "💅 Beauty (Somewhere Sunny)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Somewhere%20Sunny.mp3" },
      { value: "sorrow", label: "😢 Sorrow (Heartbreaking)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heartbreaking.mp3" },
      { value: "piano", label: "🎹 Piano (Touching Moments)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Touching%20Moments%20Two%20-%20Higher.mp3" },
      { value: "epic", label: "⚔️ Epic (Curse of Scarab)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Curse%20of%20the%20Scarab.mp3" },
      { value: "dramatic", label: "🎭 Dramatic (Volatile)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Volatile%20Reaction.mp3" },
      { value: "cinematic", label: "🎬 Cinematic (Thunderbird)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Thunderbird.mp3" },
      { value: "horror", label: "👻 Horror (The Hive)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Hive.mp3" },
      { value: "suspense", label: "😨 Suspense (Giant Wyrm)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Giant%20Wyrm.mp3" },
      { value: "scary", label: "😱 Scary (Darkness)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Gathering%20Darkness.mp3" },
      { value: "rock", label: "🎸 Rock (Malt Shop)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Malt%20Shop%20Bop.mp3" },
      { value: "action", label: "💥 Action (Movement)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Movement%20Proposition.mp3" },
      { value: "hiphop", label: "🧢 HipHop (Rollin)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Rollin%20at%205.mp3" },
      { value: "jazz", label: "🎷 Jazz (Bass Walker)", url: "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Bass%20Walker.mp3" },
  ];

  const selectedMusicUrl = MUSIC_OPTIONS.find(m => m.value === settings.musicMood)?.url;  
  // Poll job status
  useEffect(() => {
    if (!jobId || status === "COMPLETED" || status === "FAILED") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/jobs/${jobId}`);
        if (!res.ok) return;
        
        const data = await res.json();
        const currentStatus = data.status; // e.g. PROCESSING, REVIEW_PENDING
        
        // Update local status
        if (currentStatus !== status) {
          setStatus(currentStatus);
        }
        
        // Handle specific states
        if (currentStatus === "REVIEW_PENDING") {
           setStatusMessage("✅ Render Complete! Please review before upload.");
           setProgress(100);
           if (data.final_video_url) {
             setVideoUrl(data.final_video_url);
           }
        } else if (currentStatus === "COMPLETED") {
          setStatusMessage("🎉 Upload Complete!");
          setProgress(100);
          if (data.metadata?.youtube_id) {
             setYoutubeUrl(`https://youtu.be/${data.metadata.youtube_id}`);
          }
        } else if (currentStatus === "PROCESSING") {
             // Fake progress for visual feedback since we don't have granular % yet
             setProgress(prev => Math.min(prev + 1, 90));
             setStatusMessage("Building video pipeline (Images -> Grok -> FFmpeg)...");
        } else if (currentStatus === "UPLOADING") {
             setStatusMessage("Uploading to YouTube...");
             setProgress(95);
        } else if (currentStatus === "FAILED") {
            setError("Job Failed: " + (data.metadata?.error || "Unknown error"));
        }

      } catch (e) {
        console.error("Polling error", e);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobId, status]);

  const handleStartRender = async () => {
    if (!selectedNicheId) {
        alert("Please select a niche first!");
        return;
    }
    
    setStatus("QUEUED");
    setProgress(5);
    setStatusMessage("Submitting job...");
    setError(null);
    setVideoUrl(null);
    setYoutubeUrl(null);

    try {
        // Map context to API structure
        const scenes = sceneBreakdown.map((s) => ({
            voiceover_text: s.voiceover_text || s.text_to_image_prompt, // Fallback if missing
            character_pose_prompt: s.character_pose_prompt || s.text_to_image_prompt,
            background_description: s.background_description || "Detailed background",
            duration_in_seconds: s.duration_in_seconds || 10,
            camera_angle: s.camera_angle || "medium shot",
            motion_description: s.motion_description || s.image_to_video_prompt,
            character_name: "Character", // Default, could be refined
            emotion: "neutrally",
            dialogue: s.dialogue,
            // Include character reference if available (just mapped naively for now)
            // Ideally we pass specific character URLs per scene
             character_images: masterCharacters.map(c => ({
                 name: c.name,
                 imageUrl: c.imageUrl
             }))
        }));

        const payload = {
            niche_id: selectedNicheId,
            title: storyIdea.substring(0, 50) || "Untitled Video",
            description: storyNarrative.substring(0, 200) + "...",
            scenes: scenes,
            video_type: videoType
        };

        const res = await fetch("http://127.0.0.1:8000/scripts/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Failed to submit job");
        
        const data = await res.json();
        setJobId(data.job_id);
        setStatus("PROCESSING");
        
    } catch (e: any) {
        setStatus("FAILED");
        setError(e.message);
    }
  };

  // UPDATE handleStitchOnly to send music_mood
  const handleStitchOnly = async (isRetry = false) => {
    if (!selectedNicheId) {
      alert("Please select a niche first!");
      return;
    }

    // Collect video URLs from scenes
    const videoUrls = sceneBreakdown
      .filter(s => s.videoUrl)
      .map(s => s.videoUrl as string);

    if (videoUrls.length === 0) {
      alert("No scene videos found! Please generate videos for each scene first.");
      return;
    }

    setStatus("PROCESSING");
    setProgress(10);
    setStatusMessage(isRetry ? `♻️ Retrying Stitch with regenerated clips...` : `Stitching ${videoUrls.length} videos...`);
    setError(null);
    setVideoUrl(null);

    try {
      // Get niche type from selected channel name
      const selectedChannel = channels?.find(c => c.id === selectedNicheId);
      const nicheType = selectedChannel?.name?.toLowerCase() || "general";

      const res = await fetch("http://127.0.0.1:8000/videos/stitch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_urls: videoUrls,
          niche_id: selectedNicheId,
          title: storyIdea.substring(0, 30) || "Stitched Video",
          niche_type: nicheType,
          music_mood: settings.musicMood // Pass the selected mood
        })
      });
      
      // ... (rest of error handling and success) ...
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        
        // AUTO-HEALING: Regenerate Corrupt Clips
        if (res.status === 422 && errorData.code === "CORRUPT_CLIPS" && !isRetry) {
             const corruptUrls = errorData.corrupt_urls || [];
             setStatusMessage(`⚠️ Found ${corruptUrls.length} corrupt clips. Auto-regenerating...`);
             
             // Find scenes that match the corrupt URLs
             const corruptScenes = sceneBreakdown.filter(s => s.videoUrl && corruptUrls.includes(s.videoUrl));
             
             if (corruptScenes.length > 0) {
                 await Promise.all(corruptScenes.map(async (scene) => {
                     const idx = sceneBreakdown.indexOf(scene);
                     console.log(`♻️ Regenerating Scene ${idx + 1}...`);
                     
                     try {
                         // Call Single Video Generation Endpoint
                         const genRes = await fetch("http://127.0.0.1:8000/scenes/generate-video", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                scene_index: idx,
                                prompt: scene.image_to_video_prompt || "Camera movement",
                                imageUrl: scene.imageUrl,
                                niche_id: selectedNicheId,
                                camera_angle: scene.camera_angle,
                                dialogue: scene.dialogue
                            })
                         });
                         
                         if (!genRes.ok) throw new Error("Regeneration failed");
                         const genData = await genRes.json();
                         
                         // Update Context with new URL
                         updateScene(idx, { videoUrl: genData.videoUrl });
                         console.log(`✅ Scene ${idx + 1} Regenerated: ${genData.videoUrl}`);
                     } catch (err) {
                         console.error(`❌ Failed to regenerate Scene ${idx + 1}`, err);
                     }
                 }));
                 
                 // Retry the stitch once (recursively, with flag to prevent infinite loop)
                 setTimeout(() => handleStitchOnly(true), 2000); 
                 
                 setStatusMessage("✅ Corrupt clips fixed! Please click 'Stitch Videos' again to finalize.");
                 setStatus("IDLE"); // Reset so user sees the button again.
                 return; 
             }
        }
        
        throw new Error(errorData.detail || "Stitch failed");
      }

      const data = await res.json();
      
      setVideoUrl(data.final_video_url);
      setMusicUrl(data.music_url || null);
      setStatus("REVIEW_PENDING");
      setProgress(100);
      setStatusMessage("✅ Video stitched successfully! Ready for review.");

    } catch (e: any) {
      setStatus("FAILED");
      setError(e.message);
    }
  };

  // --- AUTO-RUN LOGIC ---
  useEffect(() => {
     if (isAutoRun && !hasAutoStitchRun && status === "IDLE") {
          // Check if we have videos to stitch
          const hasVideos = sceneBreakdown.some(s => s.videoUrl);
          
          if (hasVideos) {
              console.log("🤖 Auto-Run: Triggering Stitch Video Only...");
              setHasAutoStitchRun(true);
              // Call stitch (ignoring dependency warning for handleStitchOnly as it's complex to wrap)
              handleStitchOnly().then(() => {
                  // Stop Auto-Run after stitching starts/completes
                  // User said "stop there for now", implies reviewing the stitched video.
                  setIsAutoRun(false);
              });
          }
     }
     // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAutoRun, hasAutoStitchRun, status, sceneBreakdown]);

  const handleUpload = async () => {
    if (!jobId) return;
    
    setStatus("UPLOADING");
    try {
        const res = await fetch(`http://127.0.0.1:8000/videos/${jobId}/upload`, {
            method: "POST"
        });
        if (!res.ok) throw new Error("Upload trigger failed");
    } catch (e: any) {
        setError("Upload failed: " + e.message);
        setStatus("REVIEW_PENDING"); // Revert to allow retry
    }
  };
  // RENDER UI
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Render Settings</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="ken-burns"
                checked={settings.kenBurns}
                onCheckedChange={(checked) =>
                  setSettings({ ...settings, kenBurns: !!checked })
                }
              />
              <label htmlFor="ken-burns">Enable Ken Burns Effect</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="sidechain"
                checked={settings.sidechain}
                onCheckedChange={(checked) =>
                  setSettings({ ...settings, sidechain: !!checked })
                }
              />
              <label htmlFor="sidechain">Enable Sidechain Compression</label>
            </div>
          </div>
          <div className="space-y-4">
             <div className="space-y-2">
                 <label className="text-sm font-medium">Resolution</label>
                 <Select value={settings.quality} onValueChange={(v) => setSettings({...settings, quality: v})}>
                     <SelectTrigger><SelectValue/></SelectTrigger>
                     <SelectContent>
                         <SelectItem value="1080p">1080p</SelectItem>
                         <SelectItem value="4k">4K (AI Upscale)</SelectItem>
                     </SelectContent>
                 </Select>
             </div>
             
             <div className="space-y-2">
                 <label className="text-sm font-medium">Background Music</label>
                 <div className="flex gap-2">
                     <Select value={settings.musicMood} onValueChange={(v) => setSettings({...settings, musicMood: v})}>
                         <SelectTrigger className="flex-1"><SelectValue/></SelectTrigger>
                         <SelectContent>
                             {MUSIC_OPTIONS.map((opt) => (
                                 <SelectItem key={opt.value} value={opt.value}>
                                     {opt.label}
                                 </SelectItem>
                             ))}
                         </SelectContent>
                     </Select>
                     
                     {selectedMusicUrl && (
                         <Button variant="outline" size="icon" asChild title="Preview / Download">
                             <a href={selectedMusicUrl} target="_blank" rel="noopener noreferrer">
                                 <Download className="h-4 w-4" />
                             </a>
                         </Button>
                     )}
                 </div>
             </div>
          </div>
        </CardContent>
      </Card>
      
      {/* ... Pipeline Card ... */}


      <Card>
        <CardHeader>
          <CardTitle>Render Pipeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
              <div className="flex justify-between text-sm">
                  <span>Status: <strong>{status}</strong></span>
                  <span>{progress}%</span>
              </div>
              <Progress value={progress} />
              <p className="text-sm text-muted-foreground">{statusMessage}</p>
          </div>

          {error && (
              <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
              </Alert>
          )}

          {/* Review Area */}
          {status === "REVIEW_PENDING" && videoUrl && (
              <div className="border rounded-md p-4 space-y-4 bg-muted/20">
                  <h3 className="font-semibold flex items-center gap-2">
                      <CheckCircle className="text-green-500 w-5 h-5"/> 
                      Video Ready for Review
                  </h3>
                  <video controls className="w-full rounded bg-black aspect-video" src={videoUrl} />
                  
                  {musicUrl && (
                      <div className="flex items-center gap-2 text-sm text-sky-400 bg-sky-950/30 p-2 rounded border border-sky-800">
                          <span>🎵 Background Music (Isolated):</span>
                          <a href={musicUrl} target="_blank" className="underline hover:text-sky-300">Download Audio</a>
                      </div>
                  )}
                  
                  <div className="flex justify-end gap-3">
                      <Button variant="outline" onClick={() => setStatus("IDLE")}>
                          🗑️ Discard
                      </Button>
                      <Button onClick={handleUpload} className="bg-red-600 hover:bg-red-700">
                          <Upload className="w-4 h-4 mr-2"/>
                          Approve & Upload to YouTube
                      </Button>
                  </div>
              </div>
          )}

          {status === "COMPLETED" && youtubeUrl && (
              <Alert className="border-green-500 bg-green-50">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <AlertTitle className="text-green-800">Success!</AlertTitle>
                  <AlertDescription className="text-green-700">
                      Your video is live on YouTube: <a href={youtubeUrl} target="_blank" className="underline font-bold">{youtubeUrl}</a>
                  </AlertDescription>
              </Alert>
          )}

        </CardContent>
      </Card>

      <div className="flex justify-end gap-3">
        {status === "IDLE" || status === "FAILED" ? (
          <>
             <Button
                size="lg"
                variant="outline"
                onClick={() => handleStitchOnly(false)}
                disabled={!selectedNicheId}
             >
                🎬 Stitch Videos Only
             </Button>
             <Button
                size="lg"
                onClick={handleStartRender}
                disabled={!selectedNicheId}
             >
                {status === "FAILED" ? "🔄 Retry Render" : "🚀 Full Render Pipeline"}
             </Button>
          </>
        ) : (
            <Button disabled variant="secondary">
                Render in Progress...
            </Button>
        )}
      </div>
    </div>
  );
}
