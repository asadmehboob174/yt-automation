import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/videos - List all videos
export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const channelId = searchParams.get('channelId');
        const status = searchParams.get('status');
        const limit = parseInt(searchParams.get('limit') || '50');

        const where: Record<string, unknown> = {};
        if (channelId) where.channelId = channelId;
        if (status) where.status = status;

        const videos = await prisma.video.findMany({
            where,
            take: limit,
            orderBy: { createdAt: 'desc' },
            include: {
                channel: {
                    select: { name: true, nicheId: true },
                },
            },
        });

        return NextResponse.json({ videos });
    } catch (error) {
        console.error('Failed to fetch videos:', error);
        return NextResponse.json(
            { error: 'Failed to fetch videos' },
            { status: 500 }
        );
    }
}

// POST /api/videos - Create a new video
export async function POST(request: Request) {
    try {
        const body = await request.json();

        if (!body.channelId || !body.title) {
            return NextResponse.json(
                { error: 'channelId and title are required' },
                { status: 400 }
            );
        }

        const video = await prisma.video.create({
            data: {
                channelId: body.channelId,
                title: body.title,
                status: body.status || 'DRAFT',
                script: body.script || {},
                assets: body.assets || null,
                youtubeUrl: body.youtubeUrl || null,
                jobId: body.jobId || null,
            },
        });

        return NextResponse.json({ video }, { status: 201 });
    } catch (error) {
        console.error('Failed to create video:', error);
        return NextResponse.json(
            { error: 'Failed to create video' },
            { status: 500 }
        );
    }
}
