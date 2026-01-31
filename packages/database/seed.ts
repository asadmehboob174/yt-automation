
import { PrismaClient } from '@prisma/client'
import fs from 'fs'
import path from 'path'

const prisma = new PrismaClient()

async function main() {
    const channelsPath = path.join(process.cwd(), 'packages/shared/channels.json')

    if (!fs.existsSync(channelsPath)) {
        console.log('No channels.json found, skipping seed.')
        return
    }

    const rawData = fs.readFileSync(channelsPath, 'utf8')
    const channels = JSON.parse(rawData)

    console.log('Seeding channels...')

    for (const [key, config] of Object.entries(channels)) {
        // @ts-ignore
        const { channel_name, style_suffix, voice_id, anchor_image, background_music, youtube } = config

        await prisma.channel.upsert({
            where: { nicheId: key },
            update: {
                name: channel_name,
                styleSuffix: style_suffix || "",
                voiceId: voice_id || "en-US-AriaNeural",
                anchorImage: anchor_image,
                bgMusic: background_music,
                youtubeId: youtube?.channel_id,
                defaultTags: youtube?.default_tags || [],
                thumbnailStyle: youtube?.thumbnail_style
            },
            create: {
                nicheId: key,
                name: channel_name,
                styleSuffix: style_suffix || "",
                voiceId: voice_id || "en-US-AriaNeural",
                anchorImage: anchor_image,
                bgMusic: background_music,
                youtubeId: youtube?.channel_id,
                defaultTags: youtube?.default_tags || [],
                thumbnailStyle: youtube?.thumbnail_style
            }
        })
        console.log(`Synced channel: ${key}`)
    }
}

main()
    .catch((e) => {
        console.error(e)
        process.exit(1)
    })
    .finally(async () => {
        await prisma.$disconnect()
    })
