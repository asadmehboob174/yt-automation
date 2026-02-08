"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useState } from "react";

interface GeneratedImage {
  id: number;
  url: string;
  approved: boolean;
}

export function AssetGallery() {
  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerateImages = async () => {
    setIsGenerating(true);
    // TODO: Call API to generate images
    // Mock data
    setImages(
      Array(8)
        .fill(null)
        .map((_, i) => ({
          id: i + 1,
          url: "",
          approved: false,
        }))
    );
    setIsGenerating(false);
  };

  const handleRegenerate = async (id: number) => {
    // TODO: Call API to regenerate single image
    console.log("Regenerating image:", id);
  };

  const handleApproveAll = () => {
    setImages(images.map((img) => ({ ...img, approved: true })));
  };

  if (images.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-muted-foreground">No images generated yet</p>
        <Button onClick={handleGenerateImages} disabled={isGenerating}>
          {isGenerating ? "Generating..." : "🎨 Generate Images with Flux-PuLID"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {images.map((img) => (
          <Card key={img.id} className="overflow-hidden">
            <div className="aspect-video bg-muted flex items-center justify-center">
              {img.url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={img.url} alt={`Scene ${img.id}`} className="object-cover" />
              ) : (
                <span className="text-muted-foreground">Scene {img.id}</span>
              )}
            </div>
            <CardContent className="p-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => handleRegenerate(img.id)}
              >
                🔄 Regenerate
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="flex justify-end">
        <Button size="lg" onClick={handleApproveAll}>
          ✅ Approve All & Start Animation
        </Button>
      </div>
    </div>
  );
}
