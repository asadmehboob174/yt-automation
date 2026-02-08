import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

interface RouteParams {
    params: Promise<{ id: string }>;
}

// GET /api/videos/[id] - Get single video
export async function GET(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;

        const video = await prisma.video.findUnique({
            where: { id },
            include: {
                channel: true,
            },
        });

        if (!video) {
            return NextResponse.json(
                { error: 'Video not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({ video });
    } catch (error) {
        console.error('Failed to fetch video:', error);
        return NextResponse.json(
            { error: 'Failed to fetch video' },
            { status: 500 }
        );
    }
}

// PUT /api/videos/[id] - Update video
export async function PUT(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;
        const body = await request.json();

        const video = await prisma.video.update({
            where: { id },
            data: {
                title: body.title,
                status: body.status,
                script: body.script,
                assets: body.assets,
                youtubeUrl: body.youtubeUrl,
                jobId: body.jobId,
            },
        });

        return NextResponse.json({ video });
    } catch (error) {
        console.error('Failed to update video:', error);
        return NextResponse.json(
            { error: 'Failed to update video' },
            { status: 500 }
        );
    }
}

// DELETE /api/videos/[id] - Delete video
export async function DELETE(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;

        await prisma.video.delete({
            where: { id },
        });

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Failed to delete video:', error);
        return NextResponse.json(
            { error: 'Failed to delete video' },
            { status: 500 }
        );
    }
}
