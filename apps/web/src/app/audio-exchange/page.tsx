'use client';

import { useState, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowRightLeft, Download, Film, Music, Upload, Loader2, Play, Pause } from 'lucide-react';
import { toast } from 'sonner';

export default function AudioExchangePage() {
    const [video1, setVideo1] = useState<File | null>(null);
    const [video2, setVideo2] = useState<File | null>(null);
    const [processing, setProcessing] = useState(false);
    const [results, setResults] = useState<{ video1_url: string; video2_url: string } | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, setFile: (f: File | null) => void) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setResults(null); // Reset results on new upload
        }
    };

    const handleSwap = async () => {
        if (!video1 || !video2) {
            toast.error("Please upload both videos first");
            return;
        }

        setProcessing(true);
        try {
            const formData = new FormData();
            formData.append('video1', video1);
            formData.append('video2', video2);

            // Use fetch directly to avoid lib/api's JSON enforcement
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${baseUrl}/tools/swap-audio`, {
                method: 'POST',
                body: formData,
                // Do NOT set Content-Type header manually for FormData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Failed to exchange audio');
            }

            const data = await response.json();
            setResults(data);
            toast.success("Audio swapped successfully!");
        } catch (error) {
            console.error(error);
            toast.error("Failed to swap audio. Please try again.");
        } finally {
            setProcessing(false);
        }
    };

    return (
        <div className="container mx-auto py-8 max-w-5xl space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold flex items-center gap-2">
                    <Music className="h-8 w-8 text-primary" />
                    Audio Exchange
                </h1>
                <p className="text-muted-foreground text-lg">
                    Swap audio tracks between two videos instantly.
                </p>
            </div>

            <div className="grid md:grid-cols-2 gap-8 items-start relative">
                {/* Video 1 Input */}
                <Card>
                    <CardHeader>
                        <CardTitle>Video 1 - Visuals</CardTitle>
                        <CardDescription>This video's visuals + Video 2's audio</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center hover:bg-muted/50 transition-colors bg-muted/20">
                            {video1 ? (
                                <div className="space-y-2 w-full">
                                    <video src={URL.createObjectURL(video1)} controls className="w-full rounded bg-black max-h-[200px]" />
                                    <p className="text-sm font-medium truncate">{video1.name}</p>
                                    <Button variant="ghost" size="sm" onClick={() => setVideo1(null)} className="text-destructive hover:text-destructive">
                                        Remove
                                    </Button>
                                </div>
                            ) : (
                                <label className="cursor-pointer space-y-2 w-full h-full flex flex-col items-center justify-center">
                                    <Upload className="h-8 w-8 text-muted-foreground" />
                                    <span className="text-sm text-muted-foreground">Click to upload Video 1</span>
                                    <Input type="file" accept="video/*" className="hidden" onChange={(e) => handleFileChange(e, setVideo1)} />
                                </label>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Swap Action Area (Absolute centered on desktop, or in between) */}
                <div className="hidden md:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                    <Button 
                        size="icon" 
                        variant="secondary" 
                        className="h-12 w-12 rounded-full shadow-lg border"
                        onClick={handleSwap}
                        disabled={!video1 || !video2 || processing}
                    >
                        {processing ? <Loader2 className="h-6 w-6 animate-spin" /> : <ArrowRightLeft className="h-6 w-6" />}
                    </Button>
                </div>

                {/* Video 2 Input */}
                <Card>
                    <CardHeader>
                        <CardTitle>Video 2 - Visuals</CardTitle>
                        <CardDescription>This video's visuals + Video 1's audio</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center hover:bg-muted/50 transition-colors bg-muted/20">
                            {video2 ? (
                                <div className="space-y-2 w-full">
                                    <video src={URL.createObjectURL(video2)} controls className="w-full rounded bg-black max-h-[200px]" />
                                    <p className="text-sm font-medium truncate">{video2.name}</p>
                                    <Button variant="ghost" size="sm" onClick={() => setVideo2(null)} className="text-destructive hover:text-destructive">
                                        Remove
                                    </Button>
                                </div>
                            ) : (
                                <label className="cursor-pointer space-y-2 w-full h-full flex flex-col items-center justify-center">
                                    <Upload className="h-8 w-8 text-muted-foreground" />
                                    <span className="text-sm text-muted-foreground">Click to upload Video 2</span>
                                    <Input type="file" accept="video/*" className="hidden" onChange={(e) => handleFileChange(e, setVideo2)} />
                                </label>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Mobile Swap Button */}
            <div className="md:hidden flex justify-center">
                <Button 
                    size="lg" 
                    className="w-full"
                    onClick={handleSwap}
                    disabled={!video1 || !video2 || processing}
                >
                    {processing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ArrowRightLeft className="h-4 w-4 mr-2" />}
                    Swap Audio Tracks
                </Button>
            </div>


            {/* Results */}
            {results && (
                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <h2 className="text-2xl font-semibold">Results</h2>
                    <div className="grid md:grid-cols-2 gap-8">
                        {/* Result 1 */}
                        <Card className="border-green-200 bg-green-50/20">
                            <CardHeader>
                                <CardTitle className="text-base">Result 1</CardTitle>
                                <CardDescription>Video 1 Visuals + Video 2 Audio</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <video src={results.video1_url} controls className="w-full rounded bg-black shadow-sm" />
                                <Button className="w-full" asChild>
                                    <a href={results.video1_url} download={`swapped_v1_visuals.mp4`} target="_blank" rel="noreferrer">
                                        <Download className="h-4 w-4 mr-2" />
                                        Download Video
                                    </a>
                                </Button>
                            </CardContent>
                        </Card>

                        {/* Result 2 */}
                        <Card className="border-green-200 bg-green-50/20">
                            <CardHeader>
                                <CardTitle className="text-base">Result 2</CardTitle>
                                <CardDescription>Video 2 Visuals + Video 1 Audio</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <video src={results.video2_url} controls className="w-full rounded bg-black shadow-sm" />
                                <Button className="w-full" asChild>
                                    <a href={results.video2_url} download={`swapped_v2_visuals.mp4`} target="_blank" rel="noreferrer">
                                        <Download className="h-4 w-4 mr-2" />
                                        Download Video
                                    </a>
                                </Button>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
