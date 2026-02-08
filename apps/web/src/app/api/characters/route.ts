import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/characters - List all characters
export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url);
        const channelId = searchParams.get('channelId');

        const where: Record<string, unknown> = {};
        if (channelId) where.channelId = channelId;

        const characters = await prisma.character.findMany({
            where,
            orderBy: { createdAt: 'desc' },
            include: {
                channel: {
                    select: { name: true, nicheId: true },
                },
            },
        });

        return NextResponse.json({ characters });
    } catch (error) {
        console.error('Failed to fetch characters:', error);
        return NextResponse.json(
            { error: 'Failed to fetch characters' },
            { status: 500 }
        );
    }
}

// POST /api/characters - Create a new character
export async function POST(request: Request) {
    try {
        const body = await request.json();

        if (!body.channelId || !body.name || !body.imageUrl) {
            return NextResponse.json(
                { error: 'channelId, name, and imageUrl are required' },
                { status: 400 }
            );
        }

        const character = await prisma.character.create({
            data: {
                channelId: body.channelId,
                name: body.name,
                imageUrl: body.imageUrl,
            },
        });

        return NextResponse.json({ character }, { status: 201 });
    } catch (error) {
        console.error('Failed to create character:', error);
        return NextResponse.json(
            { error: 'Failed to create character' },
            { status: 500 }
        );
    }
}
