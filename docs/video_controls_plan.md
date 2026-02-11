# Implementation Plan - Video Duration & Aspect Ratio Controls

**Status:** Pending Implementation
**Date:** 2026-02-09

## Goal
Allow users to configure video generation settings, specifically **Duration** (5s vs 10s) and **Aspect Ratio** (16:9, 9:16, 2.35:1), directly from the UI. This provides more control over the Grok generation process.

## Proposed Changes

### Backend (`apps/api/main.py`)

#### [MODIFY] `apps/api/main.py`
- Update `GenerateVideoRequest` model to include:
    - `duration: Optional[int] = 5`
    - `aspect_ratio: Optional[str] = None`
- Update `/scenes/generate-video` endpoint to:
    - Receive these new parameters.
    - Pass them to `animator.animate()`.
    - Logic: Use explicit `aspect_ratio` if provided; otherwise fallback to `is_shorts` logic.

### Frontend (`apps/web`)

#### [MODIFY] `apps/web/src/lib/stores/project-store.ts`
- Update `ProjectState` interface and `initialState` to include:
    ```typescript
    videoSettings: {
        duration: 5 | 10;
        aspectRatio: '16:9' | '9:16' | '2.35:1';
    }
    ```
- Add `setVideoSettings` action.

#### [MODIFY] `apps/web/src/app/projects/new/page.tsx`
- In `Step4SceneVideos` component:
    - Add a "Settings" toolbar or section above the scene list.
    - Add `Duration` toggle (5s / 10s).
    - Add `Aspect Ratio` selector (Landscape, Portrait, Ultrawide).
    - Update `handleGenerateVideo` to pass `duration` and `aspect_ratio` from store.

## Verification Plan

### Manual Verification
1.  **Start App**: Run `npm run dev` in `apps/web` and `python apps/api/main.py`.
2.  **New Project**: Create a new project (or use existing one).
3.  **Navigate to Step 4**: Go to the "Scene Videos" step.
4.  **Check UI**: Verify "Video Settings" controls appear.
5.  **Test Configuration**:
    -   Set Duration to **5s**.
    -   Set Aspect Ratio to **2.35:1 (Cinematic)**.
6.  **Generate**: Click "Generate Video" for a scene.
7.  **Verify Backend**: Check Python console logs for:
    -   `Generating video for scene X`
    -   `Duration: 5s`
    -   `Aspect Ratio: 2.35:1`
8.  **Verify Output**: Open the generated video link and confirm it is 5 seconds long and has the correct aspect ratio.
