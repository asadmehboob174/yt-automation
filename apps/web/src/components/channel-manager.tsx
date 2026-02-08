"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ChannelManager() {
  const [channels, setChannels] = useState<any[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [formData, setFormData] = useState<any>({});
  const [characters, setCharacters] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [newCharName, setNewCharName] = useState("");
  const [isUploadingChar, setIsUploadingChar] = useState(false);

  // Fetch channels on mount
  useEffect(() => {
    fetch("http://127.0.0.1:8000/channels")
      .then((res) => res.json())
      .then((data) => setChannels(data.channels));
  }, []);

  // Fetch detailed config when channel selected
  useEffect(() => {
    if (selectedChannel && selectedChannel !== "new") {
      setLoading(true);
      Promise.all([
        fetch(`http://127.0.0.1:8000/channels/${selectedChannel}`).then(res => res.json()),
        fetch(`http://127.0.0.1:8000/channels/${selectedChannel}/characters`).then(res => res.json())
      ]).then(([channelData, charData]) => {
          setFormData(channelData);
          setCharacters(charData.characters || []);
          setLoading(false);
      });
    } else if (selectedChannel === "new") {
       setFormData({
        name: "New Channel",
        nicheId: "",
        voiceId: "en-US-AriaNeural",
        styleSuffix: "",
      });
      setCharacters([]);
    }
  }, [selectedChannel]);

  const handleCreateNew = () => {
    setSelectedChannel("new");
    setFormData({
      name: "New Channel",
      nicheId: "",
      voiceId: "en-US-AriaNeural",
      styleSuffix: "",
    });
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const isNew = selectedChannel === "new";
      const url = isNew 
        ? "http://127.0.0.1:8000/channels" 
        : `http://127.0.0.1:8000/channels/${selectedChannel}`;
      
      const method = isNew ? "POST" : "PUT";
      
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      
      if (!res.ok) throw new Error("Failed to save");
      
      const saved = await res.json();
      
      // Refresh list
      const listRes = await fetch("http://127.0.0.1:8000/channels");
      const listData = await listRes.json();
      setChannels(listData.channels);
      
      // Select the saved channel
      setSelectedChannel(saved.nicheId);
      
    } catch (error) {
      console.error(error);
      alert("Failed to save channel");
    } finally {
      setLoading(false);
    }
  };

  const handleAddCharacter = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0] || !selectedChannel || !newCharName) return;
    
    setIsUploadingChar(true);
    const file = e.target.files[0];
    const uploadData = new FormData();
    uploadData.append("file", file);
    uploadData.append("name", newCharName);
    
    try {
      const res = await fetch(`http://127.0.0.1:8000/channels/${selectedChannel}/characters`, {
        method: "POST",
        body: uploadData,
      });
      const newChar = await res.json();
      setCharacters([...characters, newChar]);
      setNewCharName(""); // Reset
    } catch (error) {
      console.error("Failed to add character", error);
    } finally {
      setIsUploadingChar(false);
    }
  };

  const handleDeleteCharacter = async (charId: string) => {
    if (!confirm("Remove this character?")) return;
    try {
      await fetch(`http://127.0.0.1:8000/characters/${charId}`, { method: "DELETE" });
      setCharacters(characters.filter(c => c.id !== charId));
    } catch (error) {
       console.error("Failed to delete", error);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: string) => {
    if (!e.target.files?.[0] || !selectedChannel) return;
    
    const file = e.target.files[0];
    const uploadData = new FormData();
    uploadData.append("file", file);
    uploadData.append("asset_type", type);
    uploadData.append("niche_id", selectedChannel);

    try {
      setLoading(true);
      const res = await fetch(`http://127.0.0.1:8000/channels/${selectedChannel}/upload`, {
        method: "POST",
        body: uploadData,
      });
      const data = await res.json();
      
      // Update form data with new URL
      if (type === "anchor") {
        setFormData({ ...formData, anchorImageUrl: data.url });
      } else {
        setFormData({ ...formData, bgMusicUrl: data.url });
      }
    } catch (error) {
      console.error("Upload failed", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-12 gap-6">
      {/* Sidebar List */}
      <div className="col-span-3 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Niches</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {channels.map((c) => (
              <Button
                key={c.id}
                variant={selectedChannel === c.id ? "default" : "outline"}
                className="w-full justify-start"
                onClick={() => setSelectedChannel(c.id)}
              >
                {c.name}
              </Button>
            ))}
            <Button 
              variant="ghost" 
              className="w-full border-dashed border-2"
              onClick={handleCreateNew}
            >
              + New Niche
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Editor Panel */}
      <div className="col-span-9">
        {(selectedChannel || selectedChannel === "new") && formData ? (
          <Card>
            <CardHeader>
              <CardTitle>Editing: {formData.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Channel Name</Label>
                  <Input 
                    value={formData.name || ""} 
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Voice ID (Edge-TTS)</Label>
                  <Select 
                    value={formData.voiceId} 
                    onValueChange={(v) => setFormData({...formData, voiceId: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="en-US-AriaNeural">en-US-AriaNeural (Female)</SelectItem>
                      <SelectItem value="en-US-GuyNeural">en-US-GuyNeural (Male)</SelectItem>
                      <SelectItem value="en-GB-SoniaNeural">en-GB-SoniaNeural (UK)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Cast & Characters */}
              <div className="space-y-3">
                 <Label className="text-lg">Cast & Characters</Label>
                 <div className="grid grid-cols-4 gap-4">
                    {/* Existing Characters */}
                    {characters.map((char) => (
                      <div key={char.id} className="relative group border rounded-lg p-2 text-center bg-muted/20">
                         <img src={char.imageUrl} className="w-full h-24 object-cover rounded mb-2" />
                         <div className="text-sm font-medium">{char.name}</div>
                         <button 
                           onClick={() => handleDeleteCharacter(char.id)}
                           className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                         >
                           <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
                         </button>
                      </div>
                    ))}

                    {/* Add New Character */}
                    <div className="border-2 border-dashed rounded-lg p-3 flex flex-col gap-2 justify-center">
                       <Input 
                         placeholder="Name (e.g. Tom)" 
                         size={10} 
                         className="h-8 text-sm"
                         value={newCharName}
                         onChange={(e) => setNewCharName(e.target.value)}
                       />
                       <div className="relative">
                         <Button variant="secondary" size="sm" className="w-full" disabled={!newCharName || isUploadingChar}>
                           {isUploadingChar ? "..." : "+ Add"}
                         </Button>
                         <Input 
                           type="file" 
                           className="absolute inset-0 opacity-0 cursor-pointer" 
                           disabled={!newCharName}
                           onChange={handleAddCharacter}
                         />
                       </div>
                    </div>
                 </div>
              </div>

              {/* Assets (Music Only now) */}
              <div className="grid grid-cols-1 gap-4">

                <div className="space-y-2">
                  <Label>Background Music</Label>
                   <div className="border-2 border-dashed rounded-lg p-4 text-center">
                    {formData.bgMusicUrl ? (
                      <audio controls src={formData.bgMusicUrl} className="w-full mb-2" />
                    ) : (
                      <div className="h-12 bg-muted flex items-center justify-center mb-2">No Audio</div>
                    )}
                    <Input type="file" accept="audio/*" onChange={(e) => handleFileUpload(e, "music")} />
                  </div>
                </div>
              </div>

              {/* Config */}
              <div className="space-y-2">
                <Label>Style Suffix Prompt</Label>
                <Textarea 
                  className="h-24"
                  value={formData.styleSuffix || ""}
                  onChange={(e) => setFormData({...formData, styleSuffix: e.target.value})}
                />
              </div>

              <div className="flex justify-end gap-3 items-end">
                 {selectedChannel === "new" && (
                   <div className="flex-1 mr-4 space-y-2">
                     <Label>Niche ID (Unique)</Label>
                     <Input 
                       placeholder="e.g. pets, history"
                       value={formData.nicheId || ""}
                       onChange={(e) => setFormData({...formData, nicheId: e.target.value})}
                     />
                   </div>
                 )}
                <Button onClick={handleSave} disabled={loading}>
                  {loading ? "Saving..." : "Save Changes"}
                </Button>
              </div>

            </CardContent>
          </Card>
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground border-2 border-dashed rounded-lg">
            Select a niche to edit
          </div>
        )}
      </div>
    </div>
  );
}
