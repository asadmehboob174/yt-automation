import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/channels - List all channels
export async function GET() {
    try {
        const channels = await prisma.channel.findMany({
            orderBy: { createdAt: 'desc' },
            include: {
                _count: {
                    select: { videos: true, characters: true },
                },
            },
        });

        return NextResponse.json({ channels });
    } catch (error) {
        console.error('Failed to fetch channels:', error);
        return NextResponse.json(
            { error: 'Failed to fetch channels' },
            { status: 500 }
        );
    }
}

// POST /api/channels - Create a new channel
export async function POST(request: Request) {
    try {
        const body = await request.json();

        // Validate required fields
        if (!body.name || !body.nicheId) {
            return NextResponse.json(
                { error: 'Name and nicheId are required' },
                { status: 400 }
            );
        }

        // Check if nicheId already exists
        const existing = await prisma.channel.findUnique({
            where: { nicheId: body.nicheId },
        });

        if (existing) {
            return NextResponse.json(
                { error: 'Channel with this nicheId already exists' },
                { status: 400 }
            );
        }

        const channel = await prisma.channel.create({
            data: {
                nicheId: body.nicheId,
                name: body.name,
                styleSuffix: body.styleSuffix || '',
                voiceId: body.voiceId || 'en-US-ChristopherNeural',
                anchorImage: body.anchorImage || null,
                bgMusic: body.bgMusic || null,
                youtubeId: body.youtubeId || null,
                defaultTags: body.defaultTags || [],
                thumbnailStyle: body.thumbnailStyle || null,
                apiToken: body.apiToken || null,
            },
        });

        return NextResponse.json({ channel }, { status: 201 });
    } catch (error) {
        console.error('Failed to create channel:', error);
        return NextResponse.json(
            { error: 'Failed to create channel' },
            { status: 500 }
        );
    }
}
