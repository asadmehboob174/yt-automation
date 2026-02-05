
const text = `🎨 CHARACTER MASTER PROMPTS (WITH CONSISTENT STYLE)
1. The Father

Text-to-Image Prompt:
A kind-faced father ...

2. The Mother

Text-to-Image Prompt:
A serene mother ...

3. The Son

Text-to-Image Prompt:
A curious 8-year-old boy ...

🎞️ SCENE PROMPTS (STYLE APPLIED TO EACH)
`;

function parseTest(text) {
    const result = { masterCharacters: [], scenes: [] };
    text = text.replace(/\r\n/g, '\n');

    let characterSection = "";
    if (/SCENE PROMPTS|SCENES?:/i.test(text)) {
        const parts = text.split(/SCENE PROMPTS|SCENES?:/i);
        characterSection = parts[0];
    } else {
        characterSection = text;
    }

    const charBracketRegex = /(?:^|\n)\s*(?:[\uD800-\uDBFF][\uDC00-\uDFFF]|[^a-zA-Z0-9\s\[])?\s*\[(.*?)\]([\s\S]*?)(?=(?:^|\n)\s*(?:[\uD800-\uDBFF][\uDC00-\uDFFF]|[^a-zA-Z0-9\s\[])?\s*\[|SCENE|$)/g;
    const charNumberedRegex = /(?:^|\n)\s*(\d+)\.\s*(.+)([\s\S]*?)(?=(?:^|\n)\s*\d+\.|SCENE|$)/gi;

    let charSearchText = characterSection;
    let charMatch;

    // Strategy A
    while ((charMatch = charBracketRegex.exec(charSearchText)) !== null) {
        result.masterCharacters.push({ name: charMatch[1] });
    }

    // Strategy B (Cascaded)
    if (result.masterCharacters.length === 0) {
        let numMatch;
        while ((numMatch = charNumberedRegex.exec(charSearchText)) !== null) {
            const name = numMatch[2].trim();
            result.masterCharacters.push({ name: name });
        }
    }

    return result;
}

const res = parseTest(text);
console.log("Found Chars:", res.masterCharacters.map(c => c.name));
