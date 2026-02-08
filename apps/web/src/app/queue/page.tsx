'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { Plus, Play, Trash2, Eye, Loader2, Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { useQueueStore } from '@/lib/stores/queue-store';
import { useAutomationStore } from '@/lib/stores/automation-store';
import { useIdleDetection, formatIdleTime } from '@/lib/hooks/use-idle';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Channel, QueueItem } from '@/types';
import { toast } from 'sonner';

const IDLE_MINUTES = 15;

export default function QueuePage() {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const { items, removeItem, updateItemStatus, getNextItem, setProcessing, isProcessing } = useQueueStore();
    const { isRunning: automationRunning, startAutomation } = useAutomationStore();
    const { isIdle, idleTime } = useIdleDetection(IDLE_MINUTES);

    // Auto-process queue when idle
    useEffect(() => {
        if (isIdle && !automationRunning && !isProcessing) {
            const nextItem = getNextItem();
            if (nextItem) {
                processQueueItem(nextItem);
            }
        }
    }, [isIdle, automationRunning, isProcessing]);

    const processQueueItem = async (item: QueueItem) => {
        setProcessing(true);
        updateItemStatus(item.id, 'processing');

        try {
            const result = await startAutomation(item.script, item.channelId, item.format);
            if (result) {
                updateItemStatus(item.id, 'done');
                toast.success(`Queue item "${item.name}" completed!`);
            } else {
                updateItemStatus(item.id, 'error', 'Automation cancelled or failed');
            }
        } catch (error) {
            updateItemStatus(item.id, 'error', error instanceof Error ? error.message : 'Unknown error');
        } finally {
            setProcessing(false);
        }
    };

    const getStatusBadge = (status: QueueItem['status']) => {
        switch (status) {
            case 'queued':
                return <Badge variant="outline"><Clock className="h-3 w-3 mr-1" />Queued</Badge>;
            case 'processing':
                return <Badge variant="secondary"><Loader2 className="h-3 w-3 mr-1 animate-spin" />Processing</Badge>;
            case 'done':
                return <Badge variant="default"><CheckCircle2 className="h-3 w-3 mr-1" />Done</Badge>;
            case 'error':
                return <Badge variant="destructive"><XCircle className="h-3 w-3 mr-1" />Error</Badge>;
        }
    };

    const schedulerStatus = automationRunning
        ? { color: 'bg-yellow-500', text: 'Paused - Automation in progress' }
        : isIdle
            ? { color: 'bg-green-500', text: 'Ready - Processing queue (idle)' }
            : { color: 'bg-gray-500', text: `Waiting - User active (${formatIdleTime(IDLE_MINUTES * 60 - idleTime)} until idle)` };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Script Queue</h1>
                    <p className="text-muted-foreground">
                        Queue scripts for automated processing
                    </p>
                </div>
                <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="mr-2 h-4 w-4" />
                            Add Script
                        </Button>
                    </DialogTrigger>
                    <AddScriptDialog onClose={() => setIsDialogOpen(false)} />
                </Dialog>
            </div>

            {/* Scheduler Status */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Scheduler Status</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${schedulerStatus.color}`} />
                        <span>{schedulerStatus.text}</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-2">
                        Runs when idle for {IDLE_MINUTES}+ minutes and no automation active
                    </p>
                </CardContent>
            </Card>

            {/* Queue Table */}
            <Card>
                <CardHeader>
                    <CardTitle>Queue Items</CardTitle>
                    <CardDescription>
                        {items.filter(i => i.status === 'queued').length} items waiting
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {items.length > 0 ? (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>#</TableHead>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Channel</TableHead>
                                    <TableHead>Format</TableHead>
                                    <TableHead>Platforms</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead className="w-[100px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {items.map((item, index) => (
                                    <TableRow key={item.id}>
                                        <TableCell>{index + 1}</TableCell>
                                        <TableCell className="font-medium">{item.name}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{item.channelId}</Badge>
                                        </TableCell>
                                        <TableCell>
                                            {item.format === 'short' ? '9:16' : '16:9'} / {item.type}
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex gap-1 flex-wrap">
                                                {item.platforms.map((p) => (
                                                    <Badge key={p} variant="secondary" className="text-xs">
                                                        {p}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </TableCell>
                                        <TableCell>{getStatusBadge(item.status)}</TableCell>
                                        <TableCell>
                                            <div className="flex gap-2">
                                                {item.status === 'queued' && (
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        onClick={() => processQueueItem(item)}
                                                        disabled={automationRunning || isProcessing}
                                                    >
                                                        <Play className="h-4 w-4" />
                                                    </Button>
                                                )}
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => {
                                                        if (confirm('Remove this item from queue?')) {
                                                            removeItem(item.id);
                                                        }
                                                    }}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    ) : (
                        <div className="text-center py-8">
                            <AlertCircle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                            <p className="text-muted-foreground">Queue is empty</p>
                            <p className="text-sm text-muted-foreground">
                                Add scripts to process them automatically when idle
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function AddScriptDialog({ onClose }: { onClose: () => void }) {
    const { addItem } = useQueueStore();
    const [name, setName] = useState('');
    const [channelId, setChannelId] = useState('');
    const [format, setFormat] = useState<'short' | 'long'>('short');
    const [type, setType] = useState<'story' | 'documentary'>('story');
    const [script, setScript] = useState('');
    const [platforms, setPlatforms] = useState<string[]>(['youtube']);

    const { data: channels } = useQuery({
        queryKey: ['channels'],
        queryFn: () => api.get<Channel[]>('/channels'),
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name || !channelId || !script) {
            toast.error('Please fill in all required fields');
            return;
        }

        addItem({
            name,
            channelId,
            format,
            type,
            script,
            platforms,
        });

        toast.success('Script added to queue');
        onClose();
    };

    const togglePlatform = (platform: string) => {
        setPlatforms((prev) =>
            prev.includes(platform)
                ? prev.filter((p) => p !== platform)
                : [...prev, platform]
        );
    };

    return (
        <DialogContent className="sm:max-w-[600px]">
            <form onSubmit={handleSubmit}>
                <DialogHeader>
                    <DialogTitle>Add to Queue</DialogTitle>
                    <DialogDescription>
                        Add a script to process automatically when idle
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="name">Name *</Label>
                        <Input
                            id="name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="My Video Project"
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label>Channel *</Label>
                        <Select value={channelId} onValueChange={setChannelId}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select a channel" />
                            </SelectTrigger>
                            <SelectContent>
                                {channels?.map((ch) => (
                                    <SelectItem key={ch.id} value={ch.nicheId}>
                                        {ch.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Format</Label>
                            <RadioGroup value={format} onValueChange={(v) => setFormat(v as 'short' | 'long')}>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="short" id="q-short" />
                                    <Label htmlFor="q-short">Short (9:16)</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="long" id="q-long" />
                                    <Label htmlFor="q-long">Long (16:9)</Label>
                                </div>
                            </RadioGroup>
                        </div>

                        <div className="space-y-2">
                            <Label>Type</Label>
                            <RadioGroup value={type} onValueChange={(v) => setType(v as 'story' | 'documentary')}>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="story" id="q-story" />
                                    <Label htmlFor="q-story">Story</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="documentary" id="q-documentary" />
                                    <Label htmlFor="q-documentary">Documentary</Label>
                                </div>
                            </RadioGroup>
                        </div>
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="script">Script *</Label>
                        <Textarea
                            id="script"
                            value={script}
                            onChange={(e) => setScript(e.target.value)}
                            placeholder="Paste your full script here..."
                            rows={8}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label>Upload To</Label>
                        <div className="flex gap-4">
                            {['youtube', 'instagram', 'tiktok', 'facebook'].map((platform) => (
                                <div key={platform} className="flex items-center space-x-2">
                                    <Switch
                                        id={`platform-${platform}`}
                                        checked={platforms.includes(platform)}
                                        onCheckedChange={() => togglePlatform(platform)}
                                        disabled={platform !== 'youtube'} // Only YouTube is implemented
                                    />
                                    <Label
                                        htmlFor={`platform-${platform}`}
                                        className={platform !== 'youtube' ? 'text-muted-foreground' : ''}
                                    >
                                        {platform.charAt(0).toUpperCase() + platform.slice(1)}
                                        {platform !== 'youtube' && ' (Soon)'}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button type="button" variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button type="submit">Add to Queue</Button>
                </DialogFooter>
            </form>
        </DialogContent>
    );
}
