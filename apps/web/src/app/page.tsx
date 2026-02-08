"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScriptEditor } from "@/components/script-editor";
import { AssetGallery } from "@/components/asset-gallery";
import { RenderPanel } from "@/components/render-panel";
import { ChannelManager } from "@/components/channel-manager";

import { ProjectProvider, useProject } from "@/context/project-context";
import { SceneImages } from "@/components/scene-images";
import { Animation } from "@/components/animation";
import { useEffect, useState } from "react";

function DashboardContent() {
  const { currentStage } = useProject();
  const [activeTab, setActiveTab] = useState("script");

  // Auto-switch tabs when stage changes
  useEffect(() => {
    if (currentStage === 3) setActiveTab("scene-images");
    if (currentStage === 4) setActiveTab("animation");
    if (currentStage === 5) setActiveTab("render");
  }, [currentStage]);

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
      <TabsList className="grid w-full grid-cols-6">
        <TabsTrigger value="script">📝 Script Editor</TabsTrigger>
        <TabsTrigger value="scene-images">🖼️ Scene Images</TabsTrigger>
        <TabsTrigger value="animation">🎬 Animation</TabsTrigger>
        <TabsTrigger value="assets">📦 Assets</TabsTrigger>
        <TabsTrigger value="render">🚀 Render</TabsTrigger>
        <TabsTrigger value="channels">📺 Channels</TabsTrigger>
      </TabsList>

      <TabsContent value="script" className="mt-6">
        <ScriptEditor />
      </TabsContent>

      <TabsContent value="scene-images" className="mt-6">
        <SceneImages />
      </TabsContent>

      <TabsContent value="animation" className="mt-6">
        <Animation />
      </TabsContent>

      <TabsContent value="assets" className="mt-6">
        <AssetGallery />
      </TabsContent>

      <TabsContent value="render" className="mt-6">
        <RenderPanel />
      </TabsContent>

      <TabsContent value="channels" className="mt-6">
        <ChannelManager />
      </TabsContent>
    </Tabs>
  );
}

export default function Dashboard() {
  return (
    <ProjectProvider>
      <DashboardContent />
    </ProjectProvider>
  );
}
