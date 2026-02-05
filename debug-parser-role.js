
const text = `🎨 CHARACTER MASTER PROMPTS
The Protagonist: Elias

Text-to-Image Prompt: A weary man in his late 30s, "A24 Horror Film" style...
Style: Authentic analog film grain...

🎞️ SCENE PROMPTS
`;

// Mock Parser Logic or import it (mocking to test the logic I plan to write)
function parseTest(text) {
    const result = { masterCharacters: [] };
    const charSearchText = text;

    // Current Strategies check
    // Strategy A: [Name] - Fail
    // Strategy B: 1. Name - Fail
    // Strategy C: Implicit - depends on regex

    // Proposed Strategy: Header lookup
    // Look for lines preceding "Text-to-Image Prompt:"
    const blocks = text.split(/Text-to-Image Prompt:/i).slice(1);
    blocks.forEach(block => {
        // We actually need the text BEFORE this block to get the name.
        // So split isn't ideal for name extraction if name is the delimiter.
        // Let's use regex to find "Text-to-Image Prompt:" and look behind.
    });

    // Better Regex Strategy:
    // Match anything that looks like a header line followed by "Text-to-Image Prompt:"
    // (?:^|\n)\s*([^\n]+?)\s*\n+Text-to-Image Prompt:

    const regex = /(?:^|\n)\s*([^\n]+?)\s*\n+Text-to-Image Prompt:/gi;
    let match;
    while ((match = regex.exec(text)) !== null) {
        let potentialName = match[1].trim();
        // Clean up "1. " or "The Protagonist: "
        // If has colon, take part after colon
        if (potentialName.includes(':')) {
            const parts = potentialName.split(':');
            potentialName = parts[parts.length - 1].trim();
        }
        // If has number prefix "1. ", remove it
        potentialName = potentialName.replace(/^\d+\.\s*/, '');

        console.log("Found Name Candidate:", potentialName);
    }
}

parseTest(text);
