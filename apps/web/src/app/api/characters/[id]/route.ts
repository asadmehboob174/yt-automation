import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

interface RouteParams {
    params: Promise<{ id: string }>;
}

// GET /api/characters/[id] - Get single character
export async function GET(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;

        const character = await prisma.character.findUnique({
            where: { id },
            include: {
                channel: {
                    select: { name: true, nicheId: true },
                },
            },
        });

        if (!character) {
            return NextResponse.json(
                { error: 'Character not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({ character });
    } catch (error) {
        console.error('Failed to fetch character:', error);
        return NextResponse.json(
            { error: 'Failed to fetch character' },
            { status: 500 }
        );
    }
}

// PUT /api/characters/[id] - Update character
export async function PUT(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;
        const body = await request.json();

        const character = await prisma.character.update({
            where: { id },
            data: {
                name: body.name,
                imageUrl: body.imageUrl,
            },
        });

        return NextResponse.json({ character });
    } catch (error) {
        console.error('Failed to update character:', error);
        return NextResponse.json(
            { error: 'Failed to update character' },
            { status: 500 }
        );
    }
}

// DELETE /api/characters/[id] - Delete character
export async function DELETE(request: Request, { params }: RouteParams) {
    try {
        const { id } = await params;

        await prisma.character.delete({
            where: { id },
        });

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Failed to delete character:', error);
        return NextResponse.json(
            { error: 'Failed to delete character' },
            { status: 500 }
        );
    }
}
