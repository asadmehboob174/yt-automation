-- CreateTable
CREATE TABLE "Channel" (
    "id" TEXT NOT NULL,
    "nicheId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "styleSuffix" TEXT NOT NULL,
    "voiceId" TEXT NOT NULL,
    "anchorImage" TEXT,
    "bgMusic" TEXT,
    "youtubeId" TEXT,
    "defaultTags" TEXT[],
    "thumbnailStyle" TEXT,
    "apiToken" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Channel_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Video" (
    "id" TEXT NOT NULL,
    "channelId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "script" JSONB NOT NULL,
    "assets" JSONB,
    "youtubeUrl" TEXT,
    "jobId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Video_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Channel_nicheId_key" ON "Channel"("nicheId");

-- AddForeignKey
ALTER TABLE "Video" ADD CONSTRAINT "Video_channelId_fkey" FOREIGN KEY ("channelId") REFERENCES "Channel"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
