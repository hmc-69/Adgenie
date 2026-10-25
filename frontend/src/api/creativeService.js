import { apiClient } from './client.js';
import { getRenderedVideoPath } from '../utils/videoPlayback.js';

const CREATIVE_GENERATION_TIMEOUT_MS = 120_000;
// Render startup may generate and upload one image per scene before submitting
// the asynchronous JSON2Video job. Each image provider call can take up to 120s.
const VIDEO_RENDER_START_TIMEOUT_MS = 300_000;

export const creativeService = {
  generateImageBrief: async (campaignId) => {
    const response = await apiClient.post(
      '/api/creative/image-brief',
      { campaign_id: Number(campaignId) },
      { timeout: CREATIVE_GENERATION_TIMEOUT_MS },
    );
    return response.data;
  },

  generateVideoScript: async (campaignId) => {
    const response = await apiClient.post(
      '/api/creative/video-script',
      { campaign_id: Number(campaignId) },
      { timeout: CREATIVE_GENERATION_TIMEOUT_MS },
    );
    return response.data;
  },

  startVideoRender: async (campaignId, creativeId) => {
    const response = await apiClient.post('/api/creative/video/render', {
      campaign_id: Number(campaignId),
      creative_id: Number(creativeId),
    }, { timeout: VIDEO_RENDER_START_TIMEOUT_MS });
    return response.data;
  },

  getVideoRenderStatus: async (campaignId, creativeId) => {
    const response = await apiClient.get(`/api/creative/campaign/${campaignId}/video/${creativeId}/status`);
    return response.data;
  },

  getRenderedVideo: async (campaignId, creativeId, videoUrl) => {
    const response = await apiClient.get(
      getRenderedVideoPath(campaignId, creativeId, videoUrl),
      { responseType: 'blob', timeout: 120000 },
    );
    return response.data;
  },

  getImageGenerationConfig: async () => {
    const response = await apiClient.get('/api/creative/image-config');
    return response.data;
  },

  generateAdvertisementImage: async (payload) => {
    const response = await apiClient.post('/api/creative/image', payload, { timeout: 180000 });
    return response.data;
  },

  getAdvertisementImage: async (campaignId, creativeId) => {
    const response = await apiClient.get(
      `/api/creative/campaign/${campaignId}/image/${creativeId}`,
      { responseType: 'blob', timeout: 30000 },
    );
    return response.data;
  },

  listCreatives: async (campaignId) => {
    const response = await apiClient.get(`/api/creative/campaign/${campaignId}`);
    return response.data;
  },

  saveCreative: async (payload) => {
    const response = await apiClient.post('/api/creative/save', payload);
    return response.data;
  },
};

export default creativeService;
