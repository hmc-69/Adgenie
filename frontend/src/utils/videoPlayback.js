export const createVideoPlaybackUrl = (videoBlob) => URL.createObjectURL(videoBlob);

export const getRenderedVideoPath = (campaignId, creativeId, videoUrl) => (
  videoUrl || `/api/creative/campaign/${campaignId}/video/${creativeId}`
);

export const isTerminalVideoStatus = (status) => ['completed', 'failed'].includes(status);
