'use client';

import { useEffect, useState, useRef } from 'react';

/**
 * Hook to detect user idle state
 * @param idleMinutes - Minutes of inactivity before considered idle (default: 15)
 * @returns boolean indicating if user is idle
 */
export function useIdleDetection(idleMinutes = 15) {
    const [isIdle, setIsIdle] = useState(false);
    const [idleTime, setIdleTime] = useState(0);
    const timeoutRef = useRef<number | undefined>(undefined);
    const intervalRef = useRef<number | undefined>(undefined);

    useEffect(() => {
        const idleMs = idleMinutes * 60 * 1000;
        let lastActivity = Date.now();

        const resetTimer = () => {
            lastActivity = Date.now();
            setIsIdle(false);
            setIdleTime(0);

            if (timeoutRef.current) {
                window.clearTimeout(timeoutRef.current);
            }
            timeoutRef.current = window.setTimeout(() => {
                setIsIdle(true);
            }, idleMs);
        };

        // Update idle time counter every second for display
        intervalRef.current = window.setInterval(() => {
            const elapsed = Date.now() - lastActivity;
            setIdleTime(Math.floor(elapsed / 1000));
        }, 1000);

        // Track user activity events
        const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
        events.forEach((e) => window.addEventListener(e, resetTimer));

        resetTimer(); // Initialize

        return () => {
            events.forEach((e) => window.removeEventListener(e, resetTimer));
            if (timeoutRef.current) {
                window.clearTimeout(timeoutRef.current);
            }
            if (intervalRef.current) {
                window.clearInterval(intervalRef.current);
            }
        };
    }, [idleMinutes]);

    return { isIdle, idleTime };
}

/**
 * Format seconds into human readable string
 */
export function formatIdleTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
}
