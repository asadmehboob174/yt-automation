
const text = `🎨 CHARACTER MASTER PROMPTS (WITH CONSISTENT STYLE)
1. The Father

Text-to-Image Prompt:
A kind-faced father in his early 40s, Studio Ghibli style, short soft black hair, wearing round silver-rimmed glasses and a thick olive-green knit sweater. He has a gentle and patient expression.
Style: Authentic Studio Ghibli hand-painted aesthetic, soft watercolor and gouache textures with visible brushstrokes, thin organic linework, nostalgic muted color palette with earthy greens and warm ambers, cinematic soft lighting, gentle depth, cozy atmosphere, high-quality 2D anime illustration, visual consistency optimized for Google Whisk.

2. The Mother

Text-to-Image Prompt:
A serene mother in her late 30s, Studio Ghibli style, long chestnut brown hair tied in a loose side-braid. She wears a cream-colored linen apron over a soft floral-print dress. Her expression is warm and welcoming with amber-colored eyes.
Style: Authentic Studio Ghibli hand-painted aesthetic, soft watercolor and gouache textures with visible brushstrokes, thin organic linework, nostalgic muted color palette with warm creams and soft florals, cinematic gentle lighting, cozy domestic mood, high-quality 2D anime illustration, Google Whisk–consistent style.

3. The Son

Text-to-Image Prompt:
A curious 8-year-old boy, Studio Ghibli style, messy dark hair and big expressive eyes. He wears a red-and-white striped t-shirt under blue denim overalls. He has a playful and energetic expression, looking slightly upwards with wonder.
Style: Authentic Studio Ghibli hand-painted aesthetic, soft watercolor and gouache textures, pastel tones, thin organic linework, nostalgic warmth, innocent whimsical character design, cinematic softness, consistent Google Whisk visual language.

🎞️ SCENE PROMPTS (STYLE APPLIED TO EACH)
GLOBAL STYLE WRAPPER (Append to all Image Prompts): Authentic analog film grain horror aesthetic, muted and desaturated color palette, high contrast lighting with deep crushed shadows, gritty texture, cinematic tension, unsettling stillness, 35mm film photography feel.

🎞️ SCENE 1 – The Rainy Road
Shot: Wide Shot
Text-to-Image Prompt: A van...
`;

function parse(text) {
    const result = {
        masterCharacters: [],
        scenes: []
    };

    text = text.replace(/\r\n/g, '\n');

    let characterSection = "";
    let sceneSection = "";

    if (/SCENE PROMPTS|SCENES?:/i.test(text)) {
        const parts = text.split(/SCENE PROMPTS|SCENES?:/i);
        characterSection = parts[0];
        sceneSection = parts[1];
    } else {
        characterSection = text;
    }

    console.log("--- Character Section ---");
    console.log(characterSection.substring(0, 500) + "...");

    let foundExplicitChars = false;
    const charNumberedRegex = /(?:^|\n)\s*(\d+)\.\s*(.+)([\s\S]*?)(?=(?:^|\n)\s*\d+\.|SCENE|$)/gi;

    let match;
    while ((match = charNumberedRegex.exec(characterSection)) !== null) {
        foundExplicitChars = true;
        const name = match[2].trim();
        console.log("Found Char:", name);
        result.masterCharacters.push({ name });
    }

    if (!foundExplicitChars) {
        console.log("No numbered characters found!");
    } else {
        console.log(`Found ${result.masterCharacters.length} characters.`);
    }
}

parse(text);
