import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

interface RouteParams {
    params: Promise<{ id: string }>;
}

// GET /api/channels/[id] - Get single channel
export async function GET(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;

        const channel = await prisma.channel.findFirst({
            where: {
                OR: [
                    { id },
                    { nicheId: id },
                ],
            },
            include: {
                characters: true,
                videos: {
                    take: 10,
                    orderBy: { createdAt: 'desc' },
                },
            },
        });

        if (!channel) {
            return NextResponse.json(
                { error: 'Channel not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({ channel });
    } catch (error) {
        console.error('Failed to fetch channel:', error);
        return NextResponse.json(
            { error: 'Failed to fetch channel' },
            { status: 500 }
        );
    }
}

// PUT /api/channels/[id] - Update channel
export async function PUT(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;
        const body = await request.json();

        const channel = await prisma.channel.update({
            where: { id },
            data: {
                name: body.name,
                styleSuffix: body.styleSuffix,
                voiceId: body.voiceId,
                anchorImage: body.anchorImage,
                bgMusic: body.bgMusic,
                youtubeId: body.youtubeId,
                defaultTags: body.defaultTags,
                thumbnailStyle: body.thumbnailStyle,
                apiToken: body.apiToken,
            },
        });

        return NextResponse.json({ channel });
    } catch (error) {
        console.error('Failed to update channel:', error);
        return NextResponse.json(
            { error: 'Failed to update channel' },
            { status: 500 }
        );
    }
}

// DELETE /api/channels/[id] - Delete channel
export async function DELETE(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;

        await prisma.channel.delete({
            where: { id },
        });

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Failed to delete channel:', error);
        return NextResponse.json(
            { error: 'Failed to delete channel' },
            { status: 500 }
        );
    }
}
