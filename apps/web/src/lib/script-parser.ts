
export interface ManualScriptData {
    stylePrompt?: string;
    masterCharacters: {
        name: string;
        prompt: string;
        imageUrl?: string;
        locked: boolean;
    }[];
    scenes: {
        scene_number: number;
        scene_title: string;
        voiceover_text: string;
        character_pose_prompt: string;
        background_description: string;
        text_to_image_prompt: string;
        image_to_video_prompt: string;
        motion_description: string;
        camera_angle: string;
        duration_in_seconds: number;
        dialogue?: string; // Explicit field
    }[];
}

export function parseManualScript(text: string): ManualScriptData {
    const result: ManualScriptData = {
        masterCharacters: [],
        scenes: []
    };

    // Normalize line endings
    text = text.replace(/\r\n/g, '\n');

    // --- 0. Pre-processing ---
    // Extract GLOBAL STYLE WRAPPER (User Request)
    // Matches "GLOBAL STYLE WRAPPER (Append to all Image Prompts):"
    const globalStyleMatch = text.match(/GLOBAL STYLE WRAPPER(?:\s*\(.*?\))?:\s*([\s\S]*?)(?=\n\n|\n[A-Z]|$)/i);
    let globalStyle = "";
    if (globalStyleMatch) {
        globalStyle = globalStyleMatch[1].trim();
        // If stylePrompt is not yet set, use extraction
        if (!result.stylePrompt) result.stylePrompt = globalStyle;
    }

    // Split into Main Sections
    let characterSection = "";
    let sceneSection = "";

    // Try explicit split markers
    if (/SCENE PROMPTS|SCENES?:/i.test(text)) {
        const parts = text.split(/SCENE PROMPTS|SCENES?:/i);
        characterSection = parts[0];
        sceneSection = parts[1];
    } else {
        // Fallback: Look for first scene marker
        const firstSceneIdx = text.search(/🎞️\s*SCENE/i);
        if (firstSceneIdx !== -1) {
            characterSection = text.substring(0, firstSceneIdx);
            sceneSection = text.substring(firstSceneIdx);
        } else {
            sceneSection = text; // Assume only scenes
        }
    }

    // --- 1. Parse Metadata ---
    // Check for "Style:" or "Style Prompt:" in character section if global wasn't found
    if (!result.stylePrompt) {
        const styleMatch = characterSection.match(/(?:Style(?: Prompt| Reference)?):\s*([\s\S]*?)(?=\n\n|\n[A-Z]|$)/i);
        if (styleMatch) {
            result.stylePrompt = styleMatch[1].trim();
        }
    }


    // --- 2. Parse Characters ---

    // Strategy A: Explicit "Emoji [Name]" or "[Name]"
    const charBracketRegex = /(?:^|\n)\s*(?:[\uD800-\uDBFF][\uDC00-\uDFFF]|[^a-zA-Z0-9\s\[])?\s*\[(.*?)\]([\s\S]*?)(?=(?:^|\n)\s*(?:[\uD800-\uDBFF][\uDC00-\uDFFF]|[^a-zA-Z0-9\s\[])?\s*\[|SCENE|$)/g;

    // Strategy B: Numbered "1. Name"
    const charNumberedRegex = /(?:^|\n)\s*(\d+)\.\s*(.+)([\s\S]*?)(?=(?:^|\n)\s*\d+\.|SCENE|$)/gi;

    // Try Bracket Format first
    let charSearchText = characterSection;
    let charMatch;

    while ((charMatch = charBracketRegex.exec(charSearchText)) !== null) {
        const name = charMatch[1].trim();
        const content = charMatch[2];
        const promptMatch = content.match(/(?:Text-to-Image Prompt:|Prompt:)\s*([\s\S]*?)$/i);
        const prompt = promptMatch ? promptMatch[1].trim() : content.trim();
        if (name && prompt) result.masterCharacters.push({ name, prompt, locked: false });
    }

    // If no brackets found (result count is 0), try Numbered Format
    if (result.masterCharacters.length === 0) {
        let numMatch;
        while ((numMatch = charNumberedRegex.exec(charSearchText)) !== null) {
            const name = numMatch[2].trim();
            const rawBlock = numMatch[3].trim();

            // Extract Prompt
            let t2i = "";
            let t2iMatch = rawBlock.match(/Text-to-Image Prompt:\s*([\s\S]*?)(?=(?:Style:|Style Prompt:|$))/i);
            if (t2iMatch) {
                t2i = t2iMatch[1].trim();
            } else {
                // Formatting fallback
                if (rawBlock.toLowerCase().includes("text-to-image prompt:")) {
                    t2i = rawBlock.split(/Text-to-Image Prompt:/i)[1].trim();
                } else {
                    t2i = rawBlock.trim(); // Assume whole block is prompt
                }
            }

            // Extract Character Style if present
            let styleMatches = rawBlock.match(/(?:Style|Style Prompt):\s*([\s\S]*?)$/i);
            let charStyle = styleMatches ? styleMatches[1].trim() : "";

            // Combine
            let finalPrompt = t2i;
            if (charStyle) finalPrompt = `${t2i}, ${charStyle}`;

            if (name && finalPrompt) {
                result.masterCharacters.push({ name, prompt: finalPrompt, locked: false });
            }
        }
    }

    // If still no characters, try Header-Based "Role: Name" or just "Name"
    if (result.masterCharacters.length === 0) {
        // Look for lines preceding "Text-to-Image Prompt:" that look like headers
        // Regex: (Start or Newline) -> (Header Text) -> (Newline(s)) -> Text-to-Image Prompt:
        const headerRegex = /(?:^|\n)\s*([^\n]+?)\s*\n+Text-to-Image Prompt:/gi;

        let headerMatch;
        while ((headerMatch = headerRegex.exec(charSearchText)) !== null) {
            let potentialName = headerMatch[1].trim();

            // Cleanup "Role: Name" -> "Name"
            // If it has a colon, take the part after the last colon (heuristic for "Role: Character Name")
            if (potentialName.includes(':')) {
                const parts = potentialName.split(':');
                potentialName = parts[parts.length - 1].trim();
            }

            // Extract the block after "Text-to-Image Prompt:" for the prompt
            // We need to find the text starting from where "Text-to-Image Prompt:" match ended
            // The regex above matches up to "Text-to-Image Prompt:", so we can find the prompt after it.
            // But strict regex for content is easier if we grab the block.

            // Let's rely on finding the prompt block relative to this header match index.
            const promptStartIndex = headerMatch.index + headerMatch[0].length;
            const remainingText = charSearchText.substring(promptStartIndex);

            // Match until next double newline, next Header, or Style line
            // We'll trust our previous block extract logic or just match until newline? 
            // Usually prompts are paragraph blocks.
            // Let's just grab until next empty line or "Style:"
            const promptContentMatch = remainingText.match(/^([\s\S]*?)(?=(?:\n\n|Style:|Style Prompt:|SCENE|$))/i);
            let prompt = promptContentMatch ? promptContentMatch[1].trim() : "";

            // Extract Style if present immediately after
            const styleMatch = remainingText.match(/(?:Style|Style Prompt):\s*([\s\S]*?)(?=(?:\n\n|SCENE|$))/i);
            const style = styleMatch ? styleMatch[1].trim() : "";

            if (style) {
                prompt = `${prompt}, ${style}`;
            }

            if (potentialName && prompt) {
                result.masterCharacters.push({ name: potentialName, prompt, locked: false });
            }
        }
    }


    // --- 3. Parse Scenes ---
    const sceneBlocks = sceneSection.split(/🎞️\s*SCENE/i).slice(1);

    sceneBlocks.forEach((block) => {
        // Match Title: "1 – The Arrival" or "1: The Arrival"
        const titleMatch = block.match(/^\s*(\d+)\s*[–:\-]\s*(.*)$/m);
        if (!titleMatch) return;

        const sceneNum = parseInt(titleMatch[1]);
        const title = titleMatch[2].trim();

        // 1. Shot Type
        const shotMatch = block.match(/(?:Shot:|Shot Type:|Shot)\s*(.*)$/m);
        const shotType = shotMatch ? shotMatch[1].trim() : "Medium Shot";

        // 2. Text-to-Image Prompt
        // Stops at next major header
        const t2iMatch = block.match(/Text-to-Image Prompt:\s*([\s\S]*?)(?=(?:Image-to-Video Prompt:|Dialogue|Sound SFX|$))/i);
        let t2iPrompt = t2iMatch ? t2iMatch[1].trim() : "";

        // Remove inline "(Style: ...)" notes if user wants clean prompts
        t2iPrompt = t2iPrompt.replace(/\(Style:.*?\)/gi, "").trim();

        // Append Global Style if it exists and wasn't already in prompt
        if (globalStyle && !t2iPrompt.includes(globalStyle)) {
            t2iPrompt = `${t2iPrompt}, ${globalStyle}`;
        }

        // 3. Image-to-Video Prompt
        const i2vMatch = block.match(/Image-to-Video Prompt:\s*([\s\S]*?)(?=(?:Dialogue|Sound SFX|$))/i);
        let i2vPrompt = i2vMatch ? i2vMatch[1].trim() : "";

        // 4. Dialogue (Flexible headers: "Dialogue:", "Dialogue (Narrator):")
        const dialogueMatch = block.match(/Dialogue.*?:(.*?)(?=(?:Sound SFX|$))/i);
        // Using 's' flag for dotAll if needed, but here simple multiline is safer
        // Actually JS dotAll is 's'. 
        // Let's stick to standard char classes for safety across environments
        const diagRegex = /Dialogue(?:.*?):\s*([\s\S]*?)(?=(?:Sound SFX|$))/i;
        const dMatch = block.match(diagRegex);
        let dialogue = dMatch ? dMatch[1].trim().replace(/^"|"$/g, '') : ""; // Remove quotes

        result.scenes.push({
            scene_number: sceneNum,
            scene_title: title,
            voiceover_text: dialogue,
            character_pose_prompt: t2iPrompt,
            background_description: "",
            text_to_image_prompt: t2iPrompt,
            image_to_video_prompt: i2vPrompt,
            motion_description: i2vPrompt,
            camera_angle: shotType,
            duration_in_seconds: Math.max(4, dialogue.length / 15),
            dialogue: dialogue // store separately
        });
    });

    return result;
}
