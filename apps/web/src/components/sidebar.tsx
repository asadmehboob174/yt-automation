"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { useNiche } from "@/context/niche-context";
import { useTheme } from "@/context/theme-context";

export function Sidebar() {
  const { channels, selectedNicheId, setSelectedNicheId, isLoading } = useNiche();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="w-72 border-r bg-card p-4 flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">🎬 AI Video Factory</h1>
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={toggleTheme}
          title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </Button>
      </div>

      <div className="space-y-3">
        <label className="text-sm font-medium">Video Format</label>
        <Select defaultValue="long-vertical">
          <SelectTrigger>
            <SelectValue placeholder="Select format" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="short">Short (9:16) - TikTok/Reels</SelectItem>
            <SelectItem value="long-vertical">Long Vertical (9:16)</SelectItem>
            <SelectItem value="standard">Standard (16:9)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-3">
        <label className="text-sm font-medium">
          Niche/Channel 
          <span className="text-xs text-muted-foreground ml-2">
            ({isLoading ? "Loading..." : `${channels?.length || 0} found`})
          </span>
        </label>
        <Select 
          value={selectedNicheId || undefined} 
          onValueChange={setSelectedNicheId}
          disabled={isLoading}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder={isLoading ? "Loading..." : "Select niche"} />
          </SelectTrigger>
          <SelectContent>
            {channels.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Separator />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Session Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">GPU Time</span>
            <Badge variant="secondary">~23 min</Badge>
          </div>
          <div className="flex justify-between">
            <span className="text-sm text-muted-foreground">Grok Gens</span>
            <Badge variant="outline">7/10</Badge>
          </div>
        </CardContent>
      </Card>
    </aside>
  );
}

