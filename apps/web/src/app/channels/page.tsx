'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
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
import { Plus, Tv, Trash2, Edit, Loader2 } from 'lucide-react';
import { db } from '@/lib/api';
import type { Channel, CreateChannelRequest } from '@/types';
import { toast } from 'sonner';
import { useForm } from 'react-hook-form';

export default function ChannelsPage() {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingChannel, setEditingChannel] = useState<Channel | null>(null);
    const queryClient = useQueryClient();

    const { data, isLoading } = useQuery({
        queryKey: ['channels'],
        queryFn: () => db.get<{ channels: Channel[] }>('/channels'),
    });
    const channels = data?.channels;

    const createMutation = useMutation({
        mutationFn: (data: CreateChannelRequest) => db.post<{ channel: Channel }>('/channels', data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['channels'] });
            toast.success('Channel created successfully');
            setIsDialogOpen(false);
        },
        onError: (error: Error) => {
            toast.error(`Failed to create channel: ${error.message}`);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => db.delete(`/channels/${id}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['channels'] });
            toast.success('Channel deleted');
        },
        onError: (error: Error) => {
            toast.error(`Failed to delete channel: ${error.message}`);
        },
    });

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Channels</h1>
                    <p className="text-muted-foreground">
                        Manage your YouTube channel configurations
                    </p>
                </div>
                <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                    <DialogTrigger asChild>
                        <Button onClick={() => setEditingChannel(null)}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add Channel
                        </Button>
                    </DialogTrigger>
                    <ChannelFormDialog
                        channel={editingChannel}
                        onSubmit={(data) => createMutation.mutate(data)}
                        isLoading={createMutation.isPending}
                        onClose={() => setIsDialogOpen(false)}
                    />
                </Dialog>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Your Channels</CardTitle>
                    <CardDescription>
                        Each channel has its own style, voice, and YouTube settings
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin" />
                        </div>
                    ) : channels && channels.length > 0 ? (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Niche ID</TableHead>
                                    <TableHead>Style</TableHead>
                                    <TableHead>Voice</TableHead>
                                    <TableHead>Tags</TableHead>
                                    <TableHead className="w-[100px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {channels.map((channel) => (
                                    <TableRow key={channel.id}>
                                        <TableCell className="font-medium">
                                            <div className="flex items-center gap-2">
                                                <Tv className="h-4 w-4 text-muted-foreground" />
                                                {channel.name}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{channel.nicheId}</Badge>
                                        </TableCell>
                                        <TableCell className="max-w-[200px] truncate">
                                            {channel.styleSuffix}
                                        </TableCell>
                                        <TableCell>{channel.voiceId}</TableCell>
                                        <TableCell>
                                            <div className="flex gap-1 flex-wrap">
                                                {channel.defaultTags.slice(0, 3).map((tag) => (
                                                    <Badge key={tag} variant="secondary" className="text-xs">
                                                        {tag}
                                                    </Badge>
                                                ))}
                                                {channel.defaultTags.length > 3 && (
                                                    <Badge variant="secondary" className="text-xs">
                                                        +{channel.defaultTags.length - 3}
                                                    </Badge>
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex gap-2">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => {
                                                        setEditingChannel(channel);
                                                        setIsDialogOpen(true);
                                                    }}
                                                >
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => {
                                                        if (confirm('Delete this channel?')) {
                                                            deleteMutation.mutate(channel.id);
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
                            <Tv className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                            <p className="text-muted-foreground">No channels yet</p>
                            <p className="text-sm text-muted-foreground">
                                Add your first channel to get started
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

function ChannelFormDialog({
    channel,
    onSubmit,
    isLoading,
    onClose,
}: {
    channel: Channel | null;
    onSubmit: (data: CreateChannelRequest) => void;
    isLoading: boolean;
    onClose: () => void;
}) {
    const { register, handleSubmit, formState: { errors } } = useForm<CreateChannelRequest>({
        defaultValues: channel
            ? {
                nicheId: channel.nicheId,
                name: channel.name,
                styleSuffix: channel.styleSuffix,
                voiceId: channel.voiceId,
                defaultTags: channel.defaultTags,
            }
            : {
                voiceId: 'en-US-AriaNeural',
                defaultTags: [],
            },
    });

    const onFormSubmit = (data: CreateChannelRequest) => {
        onSubmit({
            ...data,
            // Parse tags from comma-separated string if needed
            defaultTags: Array.isArray(data.defaultTags)
                ? data.defaultTags
                : (data.defaultTags as unknown as string).split(',').map(t => t.trim()).filter(Boolean),
        });
    };

    return (
        <DialogContent className="sm:max-w-[500px]">
            <form onSubmit={handleSubmit(onFormSubmit)}>
                <DialogHeader>
                    <DialogTitle>{channel ? 'Edit Channel' : 'Create Channel'}</DialogTitle>
                    <DialogDescription>
                        Configure your channel settings for AI video generation
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="name">Channel Name</Label>
                        <Input
                            id="name"
                            placeholder="My Pets Channel"
                            {...register('name', { required: 'Name is required' })}
                        />
                        {errors.name && (
                            <p className="text-sm text-destructive">{errors.name.message}</p>
                        )}
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="nicheId">Niche ID</Label>
                        <Input
                            id="nicheId"
                            placeholder="pets"
                            {...register('nicheId', {
                                required: 'Niche ID is required',
                                pattern: {
                                    value: /^[a-z0-9-]+$/,
                                    message: 'Only lowercase letters, numbers, and hyphens allowed'
                                }
                            })}
                            disabled={!!channel}
                        />
                        {errors.nicheId && (
                            <p className="text-sm text-destructive">{errors.nicheId.message}</p>
                        )}
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="styleSuffix">Style Suffix</Label>
                        <Textarea
                            id="styleSuffix"
                            placeholder="High-quality Pixar/Disney 3D render, soft lighting..."
                            {...register('styleSuffix', { required: 'Style is required' })}
                        />
                        {errors.styleSuffix && (
                            <p className="text-sm text-destructive">{errors.styleSuffix.message}</p>
                        )}
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="voiceId">Voice ID (Edge-TTS)</Label>
                        <Input
                            id="voiceId"
                            placeholder="en-US-AriaNeural"
                            {...register('voiceId', { required: 'Voice ID is required' })}
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="defaultTags">Default Tags (comma-separated)</Label>
                        <Input
                            id="defaultTags"
                            placeholder="AI animation, story, kids"
                            {...register('defaultTags')}
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button type="button" variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isLoading}>
                        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {channel ? 'Update' : 'Create'}
                    </Button>
                </DialogFooter>
            </form>
        </DialogContent>
    );
}
