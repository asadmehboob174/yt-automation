import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

// GET /api/health - Health check endpoint
export async function GET() {
    const checks = {
        api: 'healthy',
        database: 'unknown',
        timestamp: new Date().toISOString(),
    };

    try {
        // Test database connection
        await prisma.$queryRaw`SELECT 1`;
        checks.database = 'healthy';
    } catch (error) {
        console.error('Database health check failed:', error);
        checks.database = 'unhealthy';
    }

    const isHealthy = checks.database === 'healthy';

    return NextResponse.json(checks, {
        status: isHealthy ? 200 : 503,
    });
}
