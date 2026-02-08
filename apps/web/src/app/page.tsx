'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Film, Tv, HardDrive, CheckCircle2, XCircle, Loader2, PlusCircle } from 'lucide-react';
import Link from 'next/link';
import { db, api } from '@/lib/api';
import type { HealthResponse, StorageStats, Video } from '@/types';

export default function DashboardPage() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthResponse>('/health/full'),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: storage } = useQuery({
    queryKey: ['storage'],
    queryFn: () => api.get<StorageStats>('/storage/stats'),
  });

  const { data: videosData } = useQuery({
    queryKey: ['videos'],
    queryFn: () => db.get<{ videos: Video[] }>('/videos'),
  });
  const videos = videosData?.videos;

  const formatBytes = (bytes?: number) => {
    if (bytes === undefined || bytes === null || isNaN(bytes) || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your AI Video Factory
          </p>
        </div>
        <Button asChild>
          <Link href="/projects/new">
            <PlusCircle className="mr-2 h-4 w-4" />
            New Video
          </Link>
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Videos</CardTitle>
            <Film className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{videos?.length ?? 0}</div>
            <p className="text-xs text-muted-foreground">in database</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Processing</CardTitle>
            <Loader2 className="h-4 w-4 text-muted-foreground animate-spin" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {videos?.filter((v) => v.status === 'PROCESSING').length ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">videos in progress</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Uploaded</CardTitle>
            <Tv className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {videos?.filter((v) => v.status === 'UPLOADED').length ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">on YouTube</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {storage ? formatBytes(storage.totalSize) : '—'}
            </div>
            <p className="text-xs text-muted-foreground">
              {storage?.fileCount ?? 0} files in R2
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Health Status */}
      <Card>
        <CardHeader>
          <CardTitle>System Health</CardTitle>
          <CardDescription>Status of connected services</CardDescription>
        </CardHeader>
        <CardContent>
          {healthLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Checking services...</span>
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              <HealthBadge label="Database" ok={health?.database} />
              <HealthBadge label="R2 Storage" ok={health?.storage} />
              <HealthBadge label="Gemini API" ok={health?.gemini} />
              <HealthBadge label="HuggingFace" ok={health?.huggingface} />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Videos */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Videos</CardTitle>
          <CardDescription>Your latest video projects</CardDescription>
        </CardHeader>
        <CardContent>
          {videos && videos.length > 0 ? (
            <div className="space-y-4">
              {videos.map((video) => (
                <div
                  key={video.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div>
                    <p className="font-medium">{video.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {new Date(video.createdAt).toLocaleDateString()}
                    </p>
                  </div>
                  <Badge
                    variant={
                      video.status === 'UPLOADED'
                        ? 'default'
                        : video.status === 'PROCESSING'
                          ? 'secondary'
                          : video.status === 'ERROR'
                            ? 'destructive'
                            : 'outline'
                    }
                  >
                    {video.status}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No videos yet. Create your first one!</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function HealthBadge({ label, ok }: { label: string; ok?: boolean }) {
  return (
    <Badge variant={ok ? 'default' : 'destructive'} className="gap-1">
      {ok ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <XCircle className="h-3 w-3" />
      )}
      {label}
    </Badge>
  );
}
